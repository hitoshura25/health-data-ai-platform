# ETL Narrative Engine - Implementation Plan

An intelligent ETL worker that combines clinical domain expertise with robust idempotent processing, advanced error recovery, and comprehensive data quality validation for health data processing workflows.

## Overview

This ETL engine processes health data files from the message queue, validates data quality, transforms raw health data into intelligent clinical narratives, and outputs structured training data. The implementation combines persistent deduplication with sophisticated clinical processing to ensure reliable, intelligent data transformation.

## Architecture Goals

- **Clinical Intelligence:** Specialized processors with physiological insights and domain knowledge
- **Idempotent Processing:** Persistent deduplication to prevent duplicate processing
- **Advanced Error Recovery:** Intelligent error classification with appropriate retry strategies
- **Data Quality Focus:** Comprehensive validation with automatic quarantine for poor quality data
- **Training Data Optimization:** Rich narrative generation with metadata for AI model improvement

## Technology Stack

### Core Dependencies
```txt
aio-pika==9.3.1
pandas==2.1.0
numpy==1.24.0
avro==1.11.3
aiosqlite==0.19.0
structlog==23.2.0
tenacity==8.2.3
prometheus-client==0.19.0
pydantic-settings==2.0.3
boto3==1.34.0
```

### Clinical Processing Dependencies
```txt
scipy==1.11.0
scikit-learn==1.3.0
```

## Implementation

### 1. Project Structure
```
etl-narrative-engine/
├── core/
│   ├── __init__.py
│   ├── consumer.py
│   ├── deduplication.py
│   ├── error_recovery.py
│   └── metrics.py
├── processors/
│   ├── __init__.py
│   ├── base_processor.py
│   ├── factory.py
│   ├── blood_glucose.py
│   ├── heart_rate.py
│   ├── sleep_session.py
│   ├── steps.py
│   ├── calories.py
│   └── hrv.py
├── validation/
│   ├── __init__.py
│   ├── data_quality.py
│   └── clinical_ranges.py
├── output/
│   ├── __init__.py
│   ├── narrative_generator.py
│   └── training_formatter.py
├── config/
│   ├── __init__.py
│   └── settings.py
├── deployment/
│   ├── docker-compose.yml
│   └── Dockerfile
├── requirements.txt
└── README.md
```

### 2. Configuration (config/settings.py)
```python
from pydantic_settings import BaseSettings
from typing import Dict, List, Any

class ETLSettings(BaseSettings):
    # Message Queue
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672"
    queue_name: str = "health_data_processing"
    max_retries: int = 3

    # Storage
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str
    s3_bucket_name: str = "health-data"

    # Deduplication
    deduplication_db_path: str = "etl_processed_messages.db"
    deduplication_retention_hours: int = 168  # 1 week

    # Data Quality
    quality_threshold: float = 0.7
    enable_quarantine: bool = True
    quarantine_low_quality: bool = True

    # Processing
    max_file_size_mb: int = 100
    max_records_per_file: int = 50000
    processing_timeout_seconds: int = 300

    # Clinical Processing
    enable_clinical_insights: bool = True
    generate_recommendations: bool = True
    clinical_context_window_hours: int = 24

    # Output
    training_data_prefix: str = "training/"
    narrative_format: str = "jsonl"
    include_metadata_in_training: bool = True

    # Monitoring
    enable_metrics: bool = True
    metrics_port: int = 8003
    log_level: str = "INFO"

    # Error Recovery
    error_classification_enabled: bool = True
    retry_delays: List[int] = [30, 300, 900]  # 30s, 5m, 15m

    class Config:
        env_file = ".env"
        env_prefix = "ETL_"

settings = ETLSettings()
```

### 3. Idempotent Consumer Base (core/consumer.py)
```python
import aio_pika
import asyncio
import time
import json
import uuid
from typing import Dict, Any, Optional
from core.deduplication import PersistentDeduplicationStore
from core.error_recovery import ErrorRecoveryManager
from core.metrics import ETLMetrics
from processors.factory import ClinicalProcessingFactory
from config.settings import settings
import structlog

logger = structlog.get_logger()

class IdempotentETLConsumer:
    """Enterprise ETL consumer with comprehensive error handling and clinical intelligence"""

    def __init__(self):
        self.connection = None
        self.channel = None
        self.deduplication_store = PersistentDeduplicationStore(
            settings.deduplication_db_path,
            settings.deduplication_retention_hours
        )
        self.processing_factory = ClinicalProcessingFactory()
        self.error_recovery = ErrorRecoveryManager()
        self.metrics = ETLMetrics()
        self._consuming = False

    async def initialize(self):
        """Initialize consumer with all dependencies"""
        # Initialize deduplication store
        await self.deduplication_store.initialize()

        # Initialize message queue connection
        self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=1)

        # Initialize processing factory
        await self.processing_factory.initialize()

        logger.info("ETL consumer initialized")

    async def start_consuming(self):
        """Start consuming messages with comprehensive error handling"""
        if not self.connection:
            await self.initialize()

        queue = await self.channel.get_queue(settings.queue_name)

        async def message_handler(message: aio_pika.IncomingMessage):
            await self._process_message_safely(message)

        await queue.consume(message_handler, auto_ack=False)
        self._consuming = True

        logger.info("Started consuming messages", queue=settings.queue_name)

        # Start background tasks
        asyncio.create_task(self._periodic_cleanup())

        try:
            await asyncio.Future()  # Run forever
        except asyncio.CancelledError:
            logger.info("Consumer cancelled")
        finally:
            self._consuming = False

    async def _process_message_safely(self, message: aio_pika.IncomingMessage):
        """Process message with comprehensive safety checks and clinical intelligence"""
        start_time = time.time()
        health_message = None
        correlation_id = None

        try:
            # Parse message
            message_data = json.loads(message.body.decode())
            correlation_id = message_data.get('correlation_id', str(uuid.uuid4()))

            with structlog.contextvars.bound_contextvars(
                correlation_id=correlation_id,
                message_id=message_data.get('message_id'),
                record_type=message_data.get('record_type')
            ):
                logger.info("Processing message started",
                           s3_key=message_data.get('key'),
                           user_id=message_data.get('user_id'))

                # Check for duplicate processing
                idempotency_key = message_data.get('idempotency_key')
                if not idempotency_key:
                    # Generate fallback idempotency key
                    key_components = [
                        message_data.get('user_id', 'unknown'),
                        message_data.get('content_hash', 'unknown'),
                        message_data.get('upload_timestamp_utc', 'unknown')
                    ]
                    import hashlib
                    idempotency_key = hashlib.sha256(':'.join(key_components).encode()).hexdigest()[:16]

                if await self.deduplication_store.is_already_processed(idempotency_key):
                    logger.info("Duplicate message detected, skipping processing")
                    await message.ack()
                    self.metrics.record_duplicate_message(message_data.get('record_type', 'unknown'))
                    return

                # Mark processing started
                await self.deduplication_store.mark_processing_started(message_data, idempotency_key)

                # Process with clinical intelligence
                result = await self._process_health_data_with_intelligence(message_data)

                processing_time = time.time() - start_time

                if result.success:
                    # Mark as completed
                    await self.deduplication_store.mark_processing_completed(
                        idempotency_key,
                        processing_time,
                        result.records_processed,
                        result.narrative
                    )

                    # Acknowledge message
                    await message.ack()

                    # Record success metrics
                    self.metrics.record_processing_success(
                        record_type=message_data.get('record_type', 'unknown'),
                        processing_time=processing_time,
                        records_processed=result.records_processed,
                        quality_score=result.quality_score
                    )

                    logger.info("Message processed successfully",
                               processing_time=processing_time,
                               records_processed=result.records_processed,
                               quality_score=result.quality_score)
                else:
                    await self._handle_processing_failure(message, message_data, result, idempotency_key)

        except Exception as e:
            logger.error("Unexpected error processing message", error=str(e))
            if correlation_id:
                await self._handle_processing_failure(
                    message, message_data or {},
                    ProcessingResult(success=False, error_message=str(e)),
                    idempotency_key if 'idempotency_key' in locals() else None
                )

    async def _process_health_data_with_intelligence(self, message_data: Dict[str, Any]) -> 'ProcessingResult':
        """Process health data with clinical intelligence and comprehensive validation"""
        start_time = time.time()

        try:
            # Extract message details
            bucket = message_data['bucket']
            key = message_data['key']
            record_type = message_data['record_type']
            user_id = message_data['user_id']

            # Download file from S3
            file_content = await self._download_s3_file(bucket, key)

            if not file_content:
                return ProcessingResult(
                    success=False,
                    error_message="Failed to download file from S3"
                )

            # Comprehensive data validation
            validation_result = await self._validate_health_data(
                file_content, record_type, user_id
            )

            if not validation_result.is_valid:
                # Move to quarantine if enabled
                if settings.enable_quarantine:
                    await self._quarantine_file(key, validation_result.errors, file_content)

                    return ProcessingResult(
                        success=True,  # Quarantine is a successful outcome
                        narrative=f"File quarantined due to validation issues: {'; '.join(validation_result.errors)}",
                        processing_time_seconds=time.time() - start_time,
                        records_processed=0,
                        quality_score=validation_result.quality_score
                    )
                else:
                    return ProcessingResult(
                        success=False,
                        error_message=f"Validation failed: {'; '.join(validation_result.errors)}",
                        quality_score=validation_result.quality_score
                    )

            # Extract records from Avro file
            records = await self._extract_avro_records(file_content)

            if not records:
                return ProcessingResult(
                    success=False,
                    error_message="No records found in Avro file"
                )

            # Get appropriate clinical processor
            processor = self.processing_factory.get_processor(record_type)

            # Process with clinical intelligence
            processing_result = await processor.process_with_clinical_insights(
                records, message_data, validation_result
            )

            if processing_result.success and processing_result.narrative:
                # Generate training data output
                await self._generate_training_output(
                    processing_result.narrative,
                    message_data,
                    {
                        'duration': time.time() - start_time,
                        'record_count': len(records),
                        'quality_score': validation_result.quality_score,
                        'warnings': validation_result.warnings,
                        'clinical_insights': processing_result.clinical_insights
                    }
                )

            processing_result.processing_time_seconds = time.time() - start_time
            processing_result.records_processed = len(records)
            processing_result.quality_score = validation_result.quality_score

            return processing_result

        except Exception as e:
            return ProcessingResult(
                success=False,
                error_message=str(e),
                processing_time_seconds=time.time() - start_time
            )

    async def _handle_processing_failure(
        self,
        message: aio_pika.IncomingMessage,
        message_data: Dict[str, Any],
        result: 'ProcessingResult',
        idempotency_key: Optional[str]
    ):
        """Handle processing failures with intelligent error recovery"""

        # Classify error type
        error_type = self.error_recovery.classify_error(Exception(result.error_message))

        # Update deduplication store
        if idempotency_key:
            await self.deduplication_store.mark_processing_failed(
                idempotency_key,
                result.error_message,
                error_type.value
            )

        # Handle based on error type and retry count
        retry_count = message_data.get('retry_count', 0)

        if error_type.retriable and retry_count < settings.max_retries:
            # Schedule retry
            await self._schedule_retry(message_data, retry_count + 1, error_type)
            await message.ack()  # Acknowledge original message

            self.metrics.record_retry_attempt(
                record_type=message_data.get('record_type', 'unknown'),
                retry_count=retry_count + 1,
                error_type=error_type.value
            )

            logger.info("Message scheduled for retry",
                       retry_count=retry_count + 1,
                       error_type=error_type.value)
        else:
            # Send to dead letter queue
            await message.reject(requeue=False)

            self.metrics.record_permanent_failure(
                record_type=message_data.get('record_type', 'unknown'),
                error_type=error_type.value
            )

            logger.error("Message permanently failed",
                        retry_count=retry_count,
                        error_type=error_type.value,
                        error=result.error_message)

    async def _periodic_cleanup(self):
        """Periodic cleanup of old records and maintenance tasks"""
        while self._consuming:
            try:
                await asyncio.sleep(3600)  # Run every hour

                # Cleanup old deduplication records
                await self.deduplication_store.cleanup_old_records()

                # Update metrics
                stats = await self.deduplication_store.get_processing_stats()
                self.metrics.update_deduplication_stats(stats)

                logger.info("Periodic cleanup completed", stats=stats)

            except Exception as e:
                logger.error("Cleanup task failed", error=str(e))

    async def stop(self):
        """Stop consuming and cleanup resources"""
        self._consuming = False
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
        logger.info("ETL consumer stopped")

# Supporting classes
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ProcessingResult:
    success: bool
    narrative: Optional[str] = None
    error_message: Optional[str] = None
    processing_time_seconds: float = 0.0
    records_processed: int = 0
    quality_score: float = 1.0
    clinical_insights: Optional[Dict[str, Any]] = None

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    quality_score: float
    metadata: Dict[str, Any]
```

### 4. Clinical Processing Factory (processors/factory.py)
```python
from processors.base_processor import BaseClinicalProcessor
from processors.blood_glucose import ClinicalBloodGlucoseProcessor
from processors.heart_rate import ClinicalHeartRateProcessor
from processors.sleep_session import ClinicalSleepProcessor
from processors.steps import ClinicalStepsProcessor
from processors.calories import ClinicalCaloriesProcessor
from processors.hrv import ClinicalHRVProcessor
from typing import Dict
import structlog

logger = structlog.get_logger()

class ClinicalProcessingFactory:
    """Factory for clinical processors with domain expertise"""

    def __init__(self):
        self.processors = {}
        self._initialized = False

    async def initialize(self):
        """Initialize all clinical processors"""
        if self._initialized:
            return

        self.processors = {
            'BloodGlucoseRecord': ClinicalBloodGlucoseProcessor(),
            'HeartRateRecord': ClinicalHeartRateProcessor(),
            'SleepSessionRecord': ClinicalSleepProcessor(),
            'StepsRecord': ClinicalStepsProcessor(),
            'ActiveCaloriesBurnedRecord': ClinicalCaloriesProcessor(),
            'HeartRateVariabilityRmssdRecord': ClinicalHRVProcessor()
        }

        # Initialize each processor
        for processor_name, processor in self.processors.items():
            await processor.initialize()
            logger.debug("Clinical processor initialized", processor=processor_name)

        self._initialized = True
        logger.info("Clinical processing factory initialized")

    def get_processor(self, record_type: str) -> BaseClinicalProcessor:
        """Get appropriate clinical processor for record type"""
        processor = self.processors.get(record_type)

        if not processor:
            logger.warning(f"No specialized processor for {record_type}, using generic")
            return GenericClinicalProcessor()

        return processor

    def get_available_processors(self) -> Dict[str, str]:
        """Get list of available processors"""
        return {
            record_type: processor.__class__.__name__
            for record_type, processor in self.processors.items()
        }

class GenericClinicalProcessor(BaseClinicalProcessor):
    """Generic processor for unknown record types"""

    async def process_with_clinical_insights(self, records, message_data, validation_result):
        from core.consumer import ProcessingResult

        narrative = f"Processed {len(records)} records of type {message_data.get('record_type', 'unknown')}. "
        narrative += "No specialized clinical insights available for this data type."

        return ProcessingResult(
            success=True,
            narrative=narrative,
            clinical_insights={"generic_processing": True}
        )

    async def initialize(self):
        pass
```

### 5. Base Clinical Processor (processors/base_processor.py)
```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime
import structlog

logger = structlog.get_logger()

class BaseClinicalProcessor(ABC):
    """Base class for clinical processors with domain expertise"""

    def __init__(self):
        self.clinical_ranges = {}
        self.reference_values = {}
        self.clinical_context = {}

    @abstractmethod
    async def process_with_clinical_insights(
        self,
        records: List[Dict[str, Any]],
        message_data: Dict[str, Any],
        validation_result: Any
    ) -> 'ProcessingResult':
        """Process records with clinical domain knowledge"""
        pass

    @abstractmethod
    async def initialize(self):
        """Initialize processor-specific configurations"""
        pass

    def _extract_temporal_patterns(self, df: pd.DataFrame, timestamp_col: str) -> Dict[str, Any]:
        """Extract temporal patterns from data"""
        if df.empty or timestamp_col not in df.columns:
            return {}

        # Convert timestamps
        df[timestamp_col] = pd.to_datetime(df[timestamp_col])

        patterns = {}

        # Time of day patterns
        df['hour'] = df[timestamp_col].dt.hour
        hourly_distribution = df.groupby('hour').size().to_dict()
        patterns['hourly_distribution'] = hourly_distribution

        # Day of week patterns
        df['day_of_week'] = df[timestamp_col].dt.day_name()
        daily_distribution = df.groupby('day_of_week').size().to_dict()
        patterns['daily_distribution'] = daily_distribution

        # Data collection span
        time_span = df[timestamp_col].max() - df[timestamp_col].min()
        patterns['collection_span_hours'] = time_span.total_seconds() / 3600

        # Measurement frequency
        if len(df) > 1:
            avg_interval = time_span / (len(df) - 1)
            patterns['average_interval_minutes'] = avg_interval.total_seconds() / 60

        return patterns

    def _calculate_statistical_insights(self, values: List[float]) -> Dict[str, Any]:
        """Calculate statistical insights for clinical interpretation"""
        if not values:
            return {}

        array = np.array(values)
        insights = {
            'count': len(values),
            'mean': float(np.mean(array)),
            'median': float(np.median(array)),
            'std': float(np.std(array)),
            'min': float(np.min(array)),
            'max': float(np.max(array)),
            'range': float(np.max(array) - np.min(array)),
            'coefficient_of_variation': float(np.std(array) / np.mean(array)) if np.mean(array) != 0 else 0
        }

        # Percentiles
        insights['percentiles'] = {
            '25th': float(np.percentile(array, 25)),
            '75th': float(np.percentile(array, 75)),
            '95th': float(np.percentile(array, 95))
        }

        # Outlier detection (simple IQR method)
        q1, q3 = np.percentile(array, [25, 75])
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        outliers = array[(array < lower_bound) | (array > upper_bound)]
        insights['outliers'] = {
            'count': len(outliers),
            'values': outliers.tolist() if len(outliers) <= 10 else outliers[:10].tolist()
        }

        return insights

    def _assess_data_quality_clinical(self, records: List[Dict], expected_patterns: Dict) -> Dict[str, Any]:
        """Assess data quality from a clinical perspective"""
        quality_assessment = {
            'clinical_completeness': 0.0,
            'physiological_validity': 0.0,
            'temporal_consistency': 0.0,
            'measurement_reliability': 0.0
        }

        if not records:
            return quality_assessment

        # Clinical completeness - are required clinical fields present?
        total_fields = len(expected_patterns.get('required_fields', []))
        if total_fields > 0:
            complete_records = 0
            for record in records:
                field_count = sum(
                    1 for field in expected_patterns['required_fields']
                    if self._get_nested_value(record, field) is not None
                )
                complete_records += field_count / total_fields

            quality_assessment['clinical_completeness'] = complete_records / len(records)

        # Physiological validity - are values within expected ranges?
        if 'value_ranges' in expected_patterns:
            valid_count = 0
            total_count = 0

            for record in records:
                for field, (min_val, max_val) in expected_patterns['value_ranges'].items():
                    value = self._get_nested_value(record, field)
                    if value is not None:
                        total_count += 1
                        if min_val <= value <= max_val:
                            valid_count += 1

            if total_count > 0:
                quality_assessment['physiological_validity'] = valid_count / total_count

        return quality_assessment

    def _get_nested_value(self, record: Dict, field_path: str) -> Any:
        """Get nested value from record using dot notation"""
        keys = field_path.split('.')
        value = record

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None

        return value

    def _generate_clinical_recommendations(self, insights: Dict[str, Any], record_type: str) -> List[str]:
        """Generate clinical recommendations based on data insights"""
        recommendations = []

        # This would be customized per processor type
        # Base implementation provides framework

        if insights.get('data_quality_issues'):
            recommendations.append(
                "Consider improving data collection consistency for more reliable health insights."
            )

        if insights.get('measurement_gaps'):
            recommendations.append(
                "More frequent measurements could provide better health trend analysis."
            )

        return recommendations

    def _format_clinical_narrative(
        self,
        record_type: str,
        statistical_insights: Dict[str, Any],
        temporal_patterns: Dict[str, Any],
        clinical_assessment: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> str:
        """Format comprehensive clinical narrative"""

        narrative_parts = []

        # Header with context
        latest_timestamp = user_context.get('latest_timestamp', 'recent data')
        record_count = statistical_insights.get('count', 0)

        narrative_parts.append(
            f"Your {record_type.replace('Record', '').lower()} data from {latest_timestamp} "
            f"contains {record_count} measurements"
        )

        # Add collection timeframe if available
        if temporal_patterns.get('collection_span_hours'):
            span_hours = temporal_patterns['collection_span_hours']
            if span_hours < 24:
                narrative_parts.append(f"collected over {span_hours:.1f} hours")
            else:
                narrative_parts.append(f"collected over {span_hours/24:.1f} days")

        narrative_parts.append(".")

        return " ".join(narrative_parts)
```

### 6. Blood Glucose Processor (processors/blood_glucose.py)
```python
from processors.base_processor import BaseClinicalProcessor
from typing import List, Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger()

class ClinicalBloodGlucoseProcessor(BaseClinicalProcessor):
    """Specialized processor for blood glucose data with clinical expertise"""

    async def initialize(self):
        """Initialize glucose-specific clinical parameters"""
        self.clinical_ranges = {
            'normal_fasting': (70, 100),      # mg/dL
            'normal_postprandial': (70, 140), # mg/dL 2 hours after meal
            'prediabetic_fasting': (100, 125),
            'diabetic_fasting': (126, float('inf')),
            'hypoglycemic': (0, 70),
            'severe_hypoglycemic': (0, 54),
            'hyperglycemic': (180, float('inf'))
        }

        self.reference_values = {
            'target_range': (80, 130),  # General target for most adults
            'tight_control_range': (70, 120),  # For intensive management
            'hba1c_correlation': {
                # Average glucose to estimated HbA1c
                100: 5.0, 120: 5.5, 140: 6.0, 160: 6.5,
                180: 7.0, 200: 7.5, 220: 8.0, 240: 8.5
            }
        }

        self.meal_timing_windows = {
            'fasting': 8,      # 8+ hours since last meal
            'pre_meal': 1,     # Within 1 hour before meal
            'post_meal_1h': 1, # 1 hour after meal
            'post_meal_2h': 2, # 2 hours after meal
            'bedtime': 1       # Within 1 hour of bedtime
        }

    async def process_with_clinical_insights(self, records, message_data, validation_result):
        """Process glucose data with comprehensive clinical analysis"""
        from core.consumer import ProcessingResult

        try:
            # Convert to DataFrame for analysis
            df = self._records_to_dataframe(records)

            if df.empty:
                return ProcessingResult(
                    success=False,
                    error_message="No valid glucose data found"
                )

            # Clinical analysis
            statistical_insights = self._analyze_glucose_statistics(df)
            temporal_patterns = self._analyze_glucose_patterns(df)
            clinical_assessment = self._assess_glucose_control(df, statistical_insights)
            meal_analysis = self._analyze_meal_relationships(df)

            # Generate clinical narrative
            narrative = self._generate_glucose_narrative(
                statistical_insights,
                temporal_patterns,
                clinical_assessment,
                meal_analysis,
                message_data
            )

            # Compile clinical insights for metadata
            clinical_insights = {
                'glucose_statistics': statistical_insights,
                'temporal_patterns': temporal_patterns,
                'clinical_assessment': clinical_assessment,
                'meal_analysis': meal_analysis,
                'recommendations': self._generate_glucose_recommendations(clinical_assessment)
            }

            return ProcessingResult(
                success=True,
                narrative=narrative,
                clinical_insights=clinical_insights
            )

        except Exception as e:
            logger.error("Glucose processing failed", error=str(e))
            return ProcessingResult(
                success=False,
                error_message=f"Glucose processing error: {e}"
            )

    def _records_to_dataframe(self, records: List[Dict[str, Any]]) -> pd.DataFrame:
        """Convert Avro records to clinical DataFrame"""
        data = []

        for record in records:
            level = record.get('level', {})
            time_data = record.get('time', {})
            metadata = record.get('metadata', {})

            if level and time_data and 'inMilligramsPerDeciliter' in level:
                data.append({
                    'glucose_mg_dl': level['inMilligramsPerDeciliter'],
                    'timestamp': pd.to_datetime(time_data['epochMillis'], unit='ms'),
                    'meal_type': record.get('mealType', 'UNKNOWN'),
                    'specimen_source': record.get('specimenSource', 'UNKNOWN'),
                    'device_id': metadata.get('dataOrigin', {}).get('packageName', 'unknown')
                })

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df = df.sort_values('timestamp').reset_index(drop=True)

        return df

    def _analyze_glucose_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Comprehensive glucose statistical analysis"""
        glucose_values = df['glucose_mg_dl'].values

        basic_stats = self._calculate_statistical_insights(glucose_values)

        # Glucose-specific metrics
        glucose_stats = {
            **basic_stats,
            'time_in_range': self._calculate_time_in_range(glucose_values),
            'glycemic_variability': self._calculate_glycemic_variability(glucose_values),
            'estimated_hba1c': self._estimate_hba1c(glucose_values),
            'hypoglycemic_events': self._count_hypoglycemic_events(df),
            'hyperglycemic_events': self._count_hyperglycemic_events(df)
        }

        return glucose_stats

    def _calculate_time_in_range(self, glucose_values: np.ndarray) -> Dict[str, float]:
        """Calculate time in various glucose ranges"""
        total_readings = len(glucose_values)

        if total_readings == 0:
            return {}

        ranges = {
            'severe_hypoglycemia': np.sum(glucose_values < 54) / total_readings * 100,
            'hypoglycemia': np.sum((glucose_values >= 54) & (glucose_values < 70)) / total_readings * 100,
            'target_range': np.sum((glucose_values >= 70) & (glucose_values <= 180)) / total_readings * 100,
            'hyperglycemia': np.sum((glucose_values > 180) & (glucose_values <= 250)) / total_readings * 100,
            'severe_hyperglycemia': np.sum(glucose_values > 250) / total_readings * 100
        }

        return ranges

    def _calculate_glycemic_variability(self, glucose_values: np.ndarray) -> Dict[str, float]:
        """Calculate measures of glycemic variability"""
        if len(glucose_values) < 2:
            return {}

        # Standard deviation
        sd = np.std(glucose_values)

        # Coefficient of variation
        cv = sd / np.mean(glucose_values) * 100 if np.mean(glucose_values) > 0 else 0

        # Mean amplitude of glycemic excursions (MAGE) - simplified
        # Find peaks and troughs
        diff = np.diff(glucose_values)
        peaks = []
        troughs = []

        for i in range(1, len(diff)):
            if diff[i-1] > 0 and diff[i] <= 0:  # Peak
                peaks.append(glucose_values[i])
            elif diff[i-1] < 0 and diff[i] >= 0:  # Trough
                troughs.append(glucose_values[i])

        mage = 0
        if peaks and troughs:
            excursions = []
            for peak in peaks:
                for trough in troughs:
                    if abs(peak - trough) > sd:  # Only count significant excursions
                        excursions.append(abs(peak - trough))
            mage = np.mean(excursions) if excursions else 0

        return {
            'standard_deviation': sd,
            'coefficient_of_variation': cv,
            'mage': mage
        }

    def _estimate_hba1c(self, glucose_values: np.ndarray) -> float:
        """Estimate HbA1c from average glucose"""
        if len(glucose_values) == 0:
            return 0

        # Formula: HbA1c (%) = (average glucose mg/dL + 46.7) / 28.7
        avg_glucose = np.mean(glucose_values)
        estimated_hba1c = (avg_glucose + 46.7) / 28.7

        return round(estimated_hba1c, 1)

    def _count_hypoglycemic_events(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Count and analyze hypoglycemic events"""
        hypo_threshold = 70
        severe_hypo_threshold = 54

        hypo_readings = df[df['glucose_mg_dl'] < hypo_threshold]
        severe_hypo_readings = df[df['glucose_mg_dl'] < severe_hypo_threshold]

        # Group consecutive hypoglycemic readings into events
        hypo_events = self._group_consecutive_events(df, lambda x: x < hypo_threshold)
        severe_hypo_events = self._group_consecutive_events(df, lambda x: x < severe_hypo_threshold)

        return {
            'total_hypo_readings': len(hypo_readings),
            'total_severe_hypo_readings': len(severe_hypo_readings),
            'hypo_events': len(hypo_events),
            'severe_hypo_events': len(severe_hypo_events),
            'lowest_reading': float(df['glucose_mg_dl'].min()) if not df.empty else None
        }

    def _count_hyperglycemic_events(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Count and analyze hyperglycemic events"""
        hyper_threshold = 180
        severe_hyper_threshold = 250

        hyper_readings = df[df['glucose_mg_dl'] > hyper_threshold]
        severe_hyper_readings = df[df['glucose_mg_dl'] > severe_hyper_threshold]

        hyper_events = self._group_consecutive_events(df, lambda x: x > hyper_threshold)
        severe_hyper_events = self._group_consecutive_events(df, lambda x: x > severe_hyper_threshold)

        return {
            'total_hyper_readings': len(hyper_readings),
            'total_severe_hyper_readings': len(severe_hyper_readings),
            'hyper_events': len(hyper_events),
            'severe_hyper_events': len(severe_hyper_events),
            'highest_reading': float(df['glucose_mg_dl'].max()) if not df.empty else None
        }

    def _group_consecutive_events(self, df: pd.DataFrame, condition_func) -> List[Dict]:
        """Group consecutive readings that meet a condition into events"""
        events = []
        current_event = None

        for _, row in df.iterrows():
            if condition_func(row['glucose_mg_dl']):
                if current_event is None:
                    current_event = {
                        'start_time': row['timestamp'],
                        'readings': [row['glucose_mg_dl']],
                        'duration_minutes': 0
                    }
                else:
                    current_event['readings'].append(row['glucose_mg_dl'])
                    current_event['duration_minutes'] = (row['timestamp'] - current_event['start_time']).total_seconds() / 60
            else:
                if current_event is not None:
                    current_event['end_time'] = row['timestamp']
                    current_event['avg_value'] = np.mean(current_event['readings'])
                    events.append(current_event)
                    current_event = None

        # Handle case where last readings are part of an event
        if current_event is not None:
            current_event['end_time'] = df.iloc[-1]['timestamp']
            current_event['avg_value'] = np.mean(current_event['readings'])
            events.append(current_event)

        return events

    def _analyze_glucose_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze temporal glucose patterns"""
        patterns = self._extract_temporal_patterns(df, 'timestamp')

        # Glucose-specific pattern analysis
        df['hour'] = df['timestamp'].dt.hour

        # Dawn phenomenon check (early morning glucose rise)
        early_morning = df[df['hour'].isin([5, 6, 7])]
        if not early_morning.empty:
            dawn_avg = early_morning['glucose_mg_dl'].mean()
            overall_avg = df['glucose_mg_dl'].mean()
            patterns['dawn_phenomenon'] = {
                'early_morning_avg': dawn_avg,
                'overall_avg': overall_avg,
                'elevation': dawn_avg - overall_avg
            }

        # Peak glucose times
        glucose_by_hour = df.groupby('hour')['glucose_mg_dl'].mean()
        if not glucose_by_hour.empty:
            patterns['peak_glucose_hour'] = int(glucose_by_hour.idxmax())
            patterns['lowest_glucose_hour'] = int(glucose_by_hour.idxmin())

        return patterns

    def _analyze_meal_relationships(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze glucose patterns related to meals"""
        meal_analysis = {}

        # Group by meal type
        meal_types = df['meal_type'].unique()

        for meal_type in meal_types:
            if meal_type == 'UNKNOWN':
                continue

            meal_data = df[df['meal_type'] == meal_type]

            if not meal_data.empty:
                meal_analysis[meal_type] = {
                    'count': len(meal_data),
                    'avg_glucose': meal_data['glucose_mg_dl'].mean(),
                    'std_glucose': meal_data['glucose_mg_dl'].std(),
                    'min_glucose': meal_data['glucose_mg_dl'].min(),
                    'max_glucose': meal_data['glucose_mg_dl'].max()
                }

        return meal_analysis

    def _assess_glucose_control(self, df: pd.DataFrame, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Assess overall glucose control quality"""
        assessment = {}

        # Time in range assessment
        tir = stats.get('time_in_range', {})
        target_tir = tir.get('target_range', 0)

        if target_tir >= 70:
            assessment['control_quality'] = 'excellent'
        elif target_tir >= 50:
            assessment['control_quality'] = 'good'
        elif target_tir >= 30:
            assessment['control_quality'] = 'fair'
        else:
            assessment['control_quality'] = 'poor'

        # Variability assessment
        variability = stats.get('glycemic_variability', {})
        cv = variability.get('coefficient_of_variation', 0)

        if cv <= 36:
            assessment['variability'] = 'low'
        elif cv <= 50:
            assessment['variability'] = 'moderate'
        else:
            assessment['variability'] = 'high'

        # Hypoglycemia risk
        hypo_events = stats.get('hypoglycemic_events', {})
        severe_hypo = hypo_events.get('severe_hypo_events', 0)

        if severe_hypo > 0:
            assessment['hypoglycemia_risk'] = 'high'
        elif hypo_events.get('hypo_events', 0) > 2:
            assessment['hypoglycemia_risk'] = 'moderate'
        else:
            assessment['hypoglycemia_risk'] = 'low'

        return assessment

    def _generate_glucose_narrative(
        self,
        stats: Dict[str, Any],
        patterns: Dict[str, Any],
        assessment: Dict[str, Any],
        meal_analysis: Dict[str, Any],
        message_data: Dict[str, Any]
    ) -> str:
        """Generate comprehensive glucose narrative with clinical insights"""

        narrative_parts = []

        # Header
        record_count = stats.get('count', 0)
        avg_glucose = stats.get('mean', 0)
        upload_date = message_data.get('upload_timestamp_utc', 'recent data')

        narrative_parts.append(
            f"Your glucose monitoring data from {upload_date} shows {record_count} readings "
            f"with an average glucose level of {avg_glucose:.1f} mg/dL."
        )

        # Time in range
        tir = stats.get('time_in_range', {})
        if tir:
            target_time = tir.get('target_range', 0)
            narrative_parts.append(
                f"You spent {target_time:.1f}% of time in the target glucose range (70-180 mg/dL)."
            )

        # Control assessment
        control_quality = assessment.get('control_quality', '')
        if control_quality:
            quality_descriptions = {
                'excellent': "This indicates excellent glucose control.",
                'good': "This shows good glucose management.",
                'fair': "This suggests room for improvement in glucose control.",
                'poor': "This indicates significant glucose management challenges."
            }
            narrative_parts.append(quality_descriptions.get(control_quality, ''))

        # Hypoglycemia assessment
        hypo_events = stats.get('hypoglycemic_events', {})
        if hypo_events.get('hypo_events', 0) > 0:
            narrative_parts.append(
                f"There were {hypo_events['hypo_events']} low glucose episodes below 70 mg/dL."
            )

            if hypo_events.get('severe_hypo_events', 0) > 0:
                narrative_parts.append("Some episodes were severe (below 54 mg/dL) and require attention.")

        # Hyperglycemia assessment
        hyper_events = stats.get('hyperglycemic_events', {})
        if hyper_events.get('hyper_events', 0) > 0:
            narrative_parts.append(
                f"There were {hyper_events['hyper_events']} high glucose episodes above 180 mg/dL."
            )

        # Variability assessment
        variability = stats.get('glycemic_variability', {})
        cv = variability.get('coefficient_of_variation', 0)
        if cv > 36:
            narrative_parts.append(
                f"Your glucose variability is elevated (CV: {cv:.1f}%), "
                "suggesting inconsistent glucose patterns that may benefit from management adjustments."
            )

        # Estimated HbA1c
        estimated_hba1c = stats.get('estimated_hba1c', 0)
        if estimated_hba1c > 0:
            narrative_parts.append(
                f"Based on your average glucose, your estimated HbA1c is approximately {estimated_hba1c}%."
            )

        # Meal relationship insights
        if meal_analysis:
            postmeal_data = meal_analysis.get('AFTER_MEAL', {})
            if postmeal_data:
                postmeal_avg = postmeal_data.get('avg_glucose', 0)
                if postmeal_avg > 180:
                    narrative_parts.append(
                        "Post-meal glucose levels are elevated, which may indicate "
                        "opportunities for meal timing or medication adjustment."
                    )

        return " ".join(narrative_parts)

    def _generate_glucose_recommendations(self, assessment: Dict[str, Any]) -> List[str]:
        """Generate glucose-specific clinical recommendations"""
        recommendations = []

        control_quality = assessment.get('control_quality', '')
        variability = assessment.get('variability', '')
        hypo_risk = assessment.get('hypoglycemia_risk', '')

        if control_quality in ['fair', 'poor']:
            recommendations.append(
                "Consider discussing glucose management strategies with your healthcare provider."
            )

        if variability == 'high':
            recommendations.append(
                "Focus on consistent meal timing and carbohydrate management to reduce glucose variability."
            )

        if hypo_risk in ['moderate', 'high']:
            recommendations.append(
                "Review hypoglycemia prevention strategies and ensure you have rapid-acting glucose available."
            )

        if not recommendations:
            recommendations.append(
                "Continue your current glucose management approach and maintain regular monitoring."
            )

        return recommendations
```

### 7. Training Data Formatter (output/training_formatter.py)
```python
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError
from config.settings import settings
import structlog

logger = structlog.get_logger()

class TrainingDataFormatter:
    """Format processed narratives into training-ready JSONL with comprehensive metadata"""

    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key
        )

    async def generate_training_output(
        self,
        narrative: str,
        source_metadata: Dict[str, Any],
        processing_metadata: Dict[str, Any]
    ) -> bool:
        """Generate training-ready JSONL with comprehensive lineage and metadata"""

        try:
            # Generate instruction based on record type and context
            instruction = self._generate_contextual_instruction(source_metadata)

            # Create comprehensive training entry
            training_entry = {
                "instruction": instruction,
                "output": narrative,
                "metadata": {
                    # Source lineage
                    "source_s3_key": source_metadata.get('key'),
                    "source_bucket": source_metadata.get('bucket'),
                    "record_type": source_metadata.get('record_type'),
                    "upload_timestamp_utc": source_metadata.get('upload_timestamp_utc'),
                    "user_id": source_metadata.get('user_id'),
                    "correlation_id": source_metadata.get('correlation_id'),

                    # Processing lineage
                    "processed_utc": datetime.utcnow().isoformat(),
                    "processing_id": str(uuid.uuid4()),
                    "processor_version": "v2.0",
                    "processing_duration_seconds": processing_metadata.get('duration', 0),
                    "records_processed": processing_metadata.get('record_count', 0),

                    # Quality metrics
                    "data_quality_score": processing_metadata.get('quality_score', 1.0),
                    "validation_warnings": processing_metadata.get('warnings', []),

                    # Clinical insights metadata
                    "clinical_insights": processing_metadata.get('clinical_insights', {}),

                    # AI training optimization
                    "training_category": self._categorize_for_training(source_metadata.get('record_type')),
                    "complexity_level": self._assess_complexity(narrative),
                    "clinical_relevance": self._assess_clinical_relevance(narrative),
                    "temporal_context": self._extract_temporal_context(processing_metadata)
                }
            }

            # Convert to JSONL format
            jsonl_line = json.dumps(training_entry, separators=(',', ':'), default=str)

            # Determine output key
            training_key = self._generate_training_key(source_metadata.get('record_type'))

            # Append to training file
            success = await self._append_to_training_file(training_key, jsonl_line + "\n")

            if success:
                logger.info("Training data generated",
                           training_key=training_key,
                           processing_id=training_entry["metadata"]["processing_id"])

            return success

        except Exception as e:
            logger.error("Failed to generate training data", error=str(e))
            return False

    def _generate_contextual_instruction(self, metadata: Dict[str, Any]) -> str:
        """Generate contextual training instruction based on metadata"""
        record_type = metadata.get('record_type', 'unknown')
        upload_time = metadata.get('upload_timestamp_utc', '')
        user_context = metadata.get('user_id', 'user')

        # Parse timestamp for more natural language
        try:
            upload_dt = datetime.fromisoformat(upload_time.replace('Z', '+00:00'))
            time_description = upload_dt.strftime('%B %d, %Y')
        except:
            time_description = upload_time

        # Record type specific instructions with clinical context
        instructions = {
            'BloodGlucoseRecord': [
                f"Analyze my blood glucose data from {time_description} and provide detailed clinical insights including glucose control assessment and recommendations.",
                f"Review my glucose monitoring results from {time_description} and explain what the patterns indicate about my diabetes management.",
                f"Interpret my blood sugar readings from {time_description} with focus on time in range, variability, and hypoglycemic risk."
            ],
            'HeartRateRecord': [
                f"Analyze my heart rate patterns from {time_description} and explain what they indicate about my cardiovascular health and fitness.",
                f"Review my heart rate data from {time_description} and provide insights about exercise response and recovery patterns.",
                f"Interpret my heart rate variability and trends from {time_description} with clinical context."
            ],
            'SleepSessionRecord': [
                f"Evaluate my sleep quality and patterns from {time_description} and provide comprehensive sleep health insights.",
                f"Analyze my sleep data from {time_description} including duration, efficiency, and recommendations for improvement.",
                f"Review my sleep metrics from {time_description} and explain how they impact my overall health and recovery."
            ],
            'StepsRecord': [
                f"Analyze my physical activity and step count data from {time_description} and provide fitness insights.",
                f"Review my daily activity patterns from {time_description} and suggest improvements for better health outcomes.",
                f"Evaluate my movement and exercise data from {time_description} with focus on meeting health guidelines."
            ],
            'ActiveCaloriesBurnedRecord': [
                f"Analyze my energy expenditure and calorie burn data from {time_description} with fitness and health insights.",
                f"Review my active calorie data from {time_description} and explain how it relates to my fitness goals.",
                f"Evaluate my metabolic activity from {time_description} and provide recommendations for optimization."
            ],
            'HeartRateVariabilityRmssdRecord': [
                f"Analyze my heart rate variability data from {time_description} and explain its implications for my autonomic nervous system health.",
                f"Review my HRV metrics from {time_description} and provide insights about stress, recovery, and overall wellness.",
                f"Interpret my heart rate variability patterns from {time_description} with clinical context and recommendations."
            ]
        }

        # Get appropriate instructions for record type
        type_instructions = instructions.get(record_type, [
            f"Analyze my {record_type.replace('Record', '').lower()} health data from {time_description} and provide clinical insights."
        ])

        # Select instruction based on some variation (could be randomized for training diversity)
        import hashlib
        selection_hash = int(hashlib.md5(f"{user_context}:{record_type}:{upload_time}".encode()).hexdigest(), 16)
        selected_instruction = type_instructions[selection_hash % len(type_instructions)]

        return selected_instruction

    def _categorize_for_training(self, record_type: str) -> str:
        """Categorize data for AI training optimization"""
        categories = {
            'BloodGlucoseRecord': 'metabolic_diabetes',
            'HeartRateRecord': 'cardiovascular_fitness',
            'SleepSessionRecord': 'sleep_recovery',
            'StepsRecord': 'physical_activity',
            'ActiveCaloriesBurnedRecord': 'energy_metabolism',
            'HeartRateVariabilityRmssdRecord': 'autonomic_health'
        }
        return categories.get(record_type, 'general_health')

    def _assess_complexity(self, narrative: str) -> str:
        """Assess narrative complexity for training prioritization"""
        word_count = len(narrative.split())
        sentence_count = len([s for s in narrative.split('.') if s.strip()])

        # Check for clinical terms
        clinical_terms = [
            'hypoglycemia', 'hyperglycemia', 'glucose control', 'time in range',
            'cardiovascular', 'autonomic', 'metabolic', 'insulin', 'diabetes',
            'blood pressure', 'heart rate variability', 'sleep efficiency'
        ]

        clinical_term_count = sum(1 for term in clinical_terms if term.lower() in narrative.lower())

        if word_count > 150 and clinical_term_count >= 3:
            return "high_clinical"
        elif word_count > 100 and clinical_term_count >= 2:
            return "moderate_clinical"
        elif word_count > 50:
            return "standard"
        else:
            return "simple"

    def _assess_clinical_relevance(self, narrative: str) -> str:
        """Assess clinical relevance for training prioritization"""
        high_relevance_terms = [
            'severe', 'critical', 'concerning', 'abnormal', 'elevated',
            'low', 'high risk', 'recommend', 'consult', 'healthcare provider'
        ]

        medium_relevance_terms = [
            'target range', 'within normal', 'optimal', 'good control',
            'improvement', 'pattern', 'trend', 'variability'
        ]

        narrative_lower = narrative.lower()

        high_count = sum(1 for term in high_relevance_terms if term in narrative_lower)
        medium_count = sum(1 for term in medium_relevance_terms if term in narrative_lower)

        if high_count >= 2:
            return "high_clinical_relevance"
        elif high_count >= 1 or medium_count >= 3:
            return "medium_clinical_relevance"
        else:
            return "standard_clinical_relevance"

    def _extract_temporal_context(self, processing_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract temporal context for training optimization"""
        clinical_insights = processing_metadata.get('clinical_insights', {})

        temporal_context = {}

        # Extract time-based patterns if available
        if 'temporal_patterns' in clinical_insights:
            patterns = clinical_insights['temporal_patterns']
            temporal_context.update({
                'collection_span_hours': patterns.get('collection_span_hours', 0),
                'measurement_frequency': patterns.get('average_interval_minutes', 0),
                'time_of_day_patterns': bool(patterns.get('hourly_distribution')),
                'day_of_week_patterns': bool(patterns.get('daily_distribution'))
            })

        # Extract clinical timing if available
        if 'glucose_statistics' in clinical_insights:
            stats = clinical_insights['glucose_statistics']
            if 'hypoglycemic_events' in stats or 'hyperglycemic_events' in stats:
                temporal_context['acute_events_present'] = True

        return temporal_context

    def _generate_training_key(self, record_type: str) -> str:
        """Generate S3 key for training data"""
        # Monthly partitioning for training data
        current_date = datetime.utcnow()
        month_path = current_date.strftime("%Y/%m")

        # Category-based organization
        category = self._categorize_for_training(record_type)

        return f"{settings.training_data_prefix}{category}/{month_path}/health_journal_{current_date.strftime('%Y_%m')}.jsonl"

    async def _append_to_training_file(self, key: str, content: str) -> bool:
        """Append content to training file in S3"""
        try:
            # Try to get existing content
            try:
                response = self.s3_client.get_object(Bucket=settings.s3_bucket_name, Key=key)
                existing_content = response['Body'].read().decode('utf-8')
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    existing_content = ""
                else:
                    raise

            # Append new content
            updated_content = existing_content + content

            # Upload updated content
            self.s3_client.put_object(
                Bucket=settings.s3_bucket_name,
                Key=key,
                Body=updated_content.encode('utf-8'),
                ContentType='application/x-jsonlines',
                Metadata={
                    'content_type': 'training_data',
                    'last_updated': datetime.utcnow().isoformat()
                }
            )

            return True

        except Exception as e:
            logger.error("Failed to append to training file", key=key, error=str(e))
            return False

    async def get_training_data_stats(self) -> Dict[str, Any]:
        """Get statistics about generated training data"""
        try:
            stats = {
                "total_files": 0,
                "total_size_bytes": 0,
                "by_category": {},
                "last_updated": None
            }

            # List training data objects
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=settings.s3_bucket_name,
                Prefix=settings.training_data_prefix
            )

            for page in page_iterator:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        stats["total_files"] += 1
                        stats["total_size_bytes"] += obj['Size']

                        # Extract category from key
                        key_parts = obj['Key'].split('/')
                        if len(key_parts) >= 2:
                            category = key_parts[1]
                            if category not in stats["by_category"]:
                                stats["by_category"][category] = {
                                    "files": 0,
                                    "size_bytes": 0
                                }
                            stats["by_category"][category]["files"] += 1
                            stats["by_category"][category]["size_bytes"] += obj['Size']

                        # Track latest modification
                        if stats["last_updated"] is None or obj['LastModified'] > stats["last_updated"]:
                            stats["last_updated"] = obj['LastModified']

            return stats

        except Exception as e:
            logger.error("Failed to get training data stats", error=str(e))
            return {"error": str(e)}
```

### 8. Environment Configuration (.env.example)
```bash
# Message Queue
ETL_RABBITMQ_URL=amqp://guest:guest@localhost:5672
ETL_QUEUE_NAME=health_data_processing
ETL_MAX_RETRIES=3

# Storage
ETL_S3_ENDPOINT_URL=http://localhost:9000
ETL_S3_ACCESS_KEY=minioadmin
ETL_S3_SECRET_KEY=your-secret-key
ETL_S3_BUCKET_NAME=health-data

# Deduplication
ETL_DEDUPLICATION_DB_PATH=etl_processed_messages.db
ETL_DEDUPLICATION_RETENTION_HOURS=168

# Data Quality
ETL_QUALITY_THRESHOLD=0.7
ETL_ENABLE_QUARANTINE=true
ETL_QUARANTINE_LOW_QUALITY=true

# Processing
ETL_MAX_FILE_SIZE_MB=100
ETL_MAX_RECORDS_PER_FILE=50000
ETL_PROCESSING_TIMEOUT_SECONDS=300

# Clinical Processing
ETL_ENABLE_CLINICAL_INSIGHTS=true
ETL_GENERATE_RECOMMENDATIONS=true
ETL_CLINICAL_CONTEXT_WINDOW_HOURS=24

# Output
ETL_TRAINING_DATA_PREFIX=training/
ETL_NARRATIVE_FORMAT=jsonl
ETL_INCLUDE_METADATA_IN_TRAINING=true

# Monitoring
ETL_ENABLE_METRICS=true
ETL_METRICS_PORT=8003
ETL_LOG_LEVEL=INFO

# Error Recovery
ETL_ERROR_CLASSIFICATION_ENABLED=true
ETL_RETRY_DELAYS=[30, 300, 900]
```

## Usage Examples

### Running the ETL Consumer
```python
import asyncio
from core.consumer import IdempotentETLConsumer

async def run_etl_worker():
    consumer = IdempotentETLConsumer()

    try:
        await consumer.start_consuming()
    except KeyboardInterrupt:
        print("Shutting down ETL worker...")
        await consumer.stop()

if __name__ == "__main__":
    asyncio.run(run_etl_worker())
```

### Testing Clinical Processors
```python
from processors.blood_glucose import ClinicalBloodGlucoseProcessor
import json

async def test_glucose_processing():
    processor = ClinicalBloodGlucoseProcessor()
    await processor.initialize()

    # Sample glucose records
    records = [
        {
            "level": {"inMilligramsPerDeciliter": 120},
            "time": {"epochMillis": 1695123456000},
            "mealType": "BEFORE_MEAL"
        },
        # ... more records
    ]

    message_data = {
        "record_type": "BloodGlucoseRecord",
        "user_id": "user123",
        "upload_timestamp_utc": "2025-09-22T12:00:00Z"
    }

    result = await processor.process_with_clinical_insights(
        records, message_data, validation_result
    )

    print("Narrative:", result.narrative)
    print("Clinical Insights:", json.dumps(result.clinical_insights, indent=2))
```

## Deployment Instructions

### Development
1. **Install dependencies:** `pip install -r requirements.txt`
2. **Configure environment:** Copy `.env.example` to `.env` and configure
3. **Start dependencies:** Ensure RabbitMQ and MinIO are running
4. **Run ETL worker:** `python -m core.consumer`

### Production
1. **Build container:** `docker build -t etl-worker:latest .`
2. **Configure environment:** Set all required environment variables
3. **Deploy:** Use container orchestration or systemd service

## Monitoring and Operations

- **Prometheus Metrics:** `http://localhost:8003/metrics`
- **Processing Stats:** Query SQLite database for deduplication statistics
- **Training Data Analytics:** Use `TrainingDataFormatter.get_training_data_stats()`
- **Clinical Insights:** Stored in training data metadata for analysis

## Integration Points

- **Message Queue:** Consumes health data processing messages
- **Object Storage:** Reads raw files, writes training data, quarantines failed files
- **AI Interface:** Provides training data for model improvement
- **Monitoring:** Exports processing metrics and quality indicators

This implementation provides enterprise-grade ETL processing with sophisticated clinical intelligence, robust error handling, and comprehensive data quality management while maintaining operational simplicity through proven patterns.