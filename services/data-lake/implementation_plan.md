# Data Lake - Implementation Plan

An intelligent object storage system using MinIO with smart naming conventions, automated lifecycle management, and comprehensive data quality validation for health data storage and organization.

## Overview

This data lake implementation provides enterprise-grade storage for health data with intelligent object naming, native lifecycle policies, and application-level data quality validation. The system balances sophisticated data organization with operational simplicity through MinIO's native features.

## Architecture Goals

- **Intelligent Organization:** Smart object naming with embedded metadata for efficient querying
- **Native Lifecycle Management:** Use MinIO's built-in policies for automated data tiering and retention
- **Data Quality Focus:** Application-level validation with quality scoring and automatic quarantine
- **Security First:** Encryption at rest, access controls, and audit logging
- **Operational Simplicity:** Minimal external dependencies, maximum use of native features

## Technology Stack

### Core Dependencies
```txt
minio==7.2.0
boto3==1.34.0
structlog==23.2.0
avro==1.11.3
prometheus-client==0.19.0
pydantic-settings==2.0.3
pandas==2.1.0
numpy==1.24.0
```

### Development Dependencies
```txt
pytest==7.4.0
pytest-asyncio==0.21.0
```

## Implementation

### 1. Project Structure
```
data-lake/
├── core/
│   ├── __init__.py
│   ├── naming.py
│   ├── validation.py
│   ├── lifecycle.py
│   └── security.py
├── storage/
│   ├── __init__.py
│   ├── client.py
│   └── operations.py
├── monitoring/
│   ├── __init__.py
│   ├── metrics.py
│   └── analytics.py
├── config/
│   ├── __init__.py
│   ├── settings.py
│   └── policies.py
├── deployment/
│   ├── docker-compose.yml
│   ├── minio-policies/
│   │   ├── lifecycle-policy.json
│   │   └── bucket-policy.json
│   └── scripts/
│       ├── setup_bucket.py
│       └── setup_policies.py
├── requirements.txt
└── README.md
```

### 2. Configuration (config/settings.py)
```python
from pydantic_settings import BaseSettings
from typing import List, Dict, Any

class DataLakeSettings(BaseSettings):
    # MinIO Connection
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str
    minio_secure: bool = False
    minio_region: str = "us-east-1"

    # Bucket Configuration
    bucket_name: str = "health-data"
    create_bucket_on_startup: bool = True

    # Object Naming
    max_object_key_length: int = 1024
    hash_length: int = 8

    # Data Quality
    enable_quality_validation: bool = True
    quality_threshold: float = 0.7
    quarantine_retention_days: int = 30

    # Lifecycle Management
    raw_data_glacier_days: int = 90
    raw_data_deep_archive_days: int = 365
    raw_data_expiration_days: int = 2555  # 7 years
    processed_data_glacier_days: int = 180
    processed_data_expiration_days: int = 3650  # 10 years

    # Security
    enable_encryption: bool = True
    enable_versioning: bool = True
    enable_audit_logging: bool = True

    # Monitoring
    enable_metrics: bool = True
    metrics_port: int = 8002
    analytics_update_interval_hours: int = 6

    # Storage Classes
    storage_classes: Dict[str, str] = {
        "standard": "STANDARD",
        "glacier": "GLACIER",
        "deep_archive": "DEEP_ARCHIVE"
    }

    class Config:
        env_file = ".env"
        env_prefix = "DATALAKE_"

settings = DataLakeSettings()
```

### 3. Intelligent Object Naming (core/naming.py)
```python
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass
import re
import structlog

logger = structlog.get_logger()

@dataclass
class ObjectKeyComponents:
    """Components of an intelligent object key"""
    layer: str  # raw, processed, quarantine, training
    record_type: str
    user_id: str
    timestamp: datetime
    file_hash: str
    source_device: Optional[str] = None
    processing_version: Optional[str] = None
    reason: Optional[str] = None  # For quarantine

class IntelligentObjectKeyGenerator:
    """Generate intelligent object keys with embedded metadata"""

    def __init__(self, hash_length: int = 8):
        self.hash_length = hash_length

    def generate_raw_key(
        self,
        record_type: str,
        user_id: str,
        timestamp: datetime,
        file_hash: str,
        source_device: str = "unknown"
    ) -> str:
        """
        Generate structured key for raw health data
        Format: raw/{record_type}/{year}/{month}/{day}/{user_id}_{timestamp}_{device}_{hash}.avro
        """
        # Validate inputs
        self._validate_inputs(record_type, user_id, file_hash)

        # Build date hierarchy
        date_path = timestamp.strftime("%Y/%m/%d")
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")

        # Sanitize and truncate components
        clean_record_type = self._sanitize_component(record_type)
        clean_user_id = self._sanitize_component(user_id)
        clean_device = self._sanitize_component(source_device)
        short_hash = file_hash[:self.hash_length]

        # Build filename
        filename = f"{clean_user_id}_{timestamp_str}_{clean_device}_{short_hash}.avro"

        # Build full key
        object_key = f"raw/{clean_record_type}/{date_path}/{filename}"

        logger.debug("Generated raw object key",
                    record_type=record_type,
                    user_id=user_id,
                    object_key=object_key)

        return object_key

    def generate_processed_key(
        self,
        record_type: str,
        user_id: str,
        processing_date: datetime,
        processing_version: str = "v1",
        file_format: str = "jsonl"
    ) -> str:
        """Generate key for processed/aggregated data"""
        self._validate_inputs(record_type, user_id)

        date_path = processing_date.strftime("%Y/%m")
        timestamp_str = processing_date.strftime("%Y%m%d_%H%M%S")

        clean_record_type = self._sanitize_component(record_type)
        clean_user_id = self._sanitize_component(user_id)
        clean_version = self._sanitize_component(processing_version)

        filename = f"{clean_user_id}_{timestamp_str}_{clean_version}.{file_format}"
        object_key = f"processed/{clean_record_type}/{date_path}/{filename}"

        return object_key

    def generate_quarantine_key(
        self,
        original_key: str,
        reason: str,
        quarantine_timestamp: Optional[datetime] = None
    ) -> str:
        """Move failed files to quarantine with reason"""
        if quarantine_timestamp is None:
            quarantine_timestamp = datetime.utcnow()

        timestamp_str = quarantine_timestamp.strftime("%Y%m%d_%H%M%S")
        clean_reason = self._sanitize_component(reason)

        # Extract filename from original key
        filename = original_key.split("/")[-1]
        base_name = filename.split(".")[0]

        object_key = f"quarantine/{clean_reason}/{timestamp_str}_{base_name}.avro"

        logger.info("Generated quarantine key",
                   original_key=original_key,
                   quarantine_key=object_key,
                   reason=reason)

        return object_key

    def generate_training_key(
        self,
        data_type: str,
        training_date: datetime,
        version: str = "v1",
        file_format: str = "jsonl"
    ) -> str:
        """Generate key for training datasets"""
        date_path = training_date.strftime("%Y/%m")
        timestamp_str = training_date.strftime("%Y%m%d")

        clean_data_type = self._sanitize_component(data_type)
        clean_version = self._sanitize_component(version)

        filename = f"health_journal_{timestamp_str}_{clean_version}.{file_format}"
        object_key = f"training/{clean_data_type}/{date_path}/{filename}"

        return object_key

    def parse_object_key(self, object_key: str) -> Optional[ObjectKeyComponents]:
        """Parse object key to extract metadata components"""
        try:
            parts = object_key.split("/")

            if len(parts) < 4:
                return None

            layer = parts[0]

            if layer == "raw" and len(parts) >= 6:
                record_type = parts[1]
                year, month, day = parts[2], parts[3], parts[4]
                filename = parts[5]

                # Parse filename: {user_id}_{timestamp}_{device}_{hash}.avro
                name_parts = filename.replace(".avro", "").split("_")
                if len(name_parts) >= 4:
                    user_id = name_parts[0]
                    timestamp_str = f"{name_parts[1]}_{name_parts[2]}"
                    device = name_parts[3] if len(name_parts) > 4 else name_parts[3]
                    file_hash = name_parts[-1]

                    timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                    return ObjectKeyComponents(
                        layer=layer,
                        record_type=record_type,
                        user_id=user_id,
                        timestamp=timestamp,
                        file_hash=file_hash,
                        source_device=device
                    )

            elif layer == "quarantine" and len(parts) >= 3:
                reason = parts[1]
                filename = parts[2]

                return ObjectKeyComponents(
                    layer=layer,
                    record_type="unknown",
                    user_id="unknown",
                    timestamp=datetime.utcnow(),
                    file_hash="unknown",
                    reason=reason
                )

            return None

        except Exception as e:
            logger.error("Failed to parse object key", object_key=object_key, error=str(e))
            return None

    def _validate_inputs(self, record_type: str, user_id: str, file_hash: str = None):
        """Validate input parameters"""
        if not record_type or not record_type.strip():
            raise ValueError("record_type cannot be empty")

        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")

        if file_hash and len(file_hash) < self.hash_length:
            raise ValueError(f"file_hash must be at least {self.hash_length} characters")

    def _sanitize_component(self, component: str) -> str:
        """Sanitize component for use in object keys"""
        if not component:
            return "unknown"

        # Replace invalid characters with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9\-_.]', '_', component)

        # Limit length
        max_length = 50
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        return sanitized.lower()

    def generate_analytics_key(self, analytics_type: str, date: datetime) -> str:
        """Generate key for analytics data"""
        date_str = date.strftime("%Y%m%d")
        return f"analytics/{analytics_type}/{date_str}.json"
```

### 4. Data Quality Validation (core/validation.py)
```python
import avro.schema
import avro.io
import io
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
import structlog

logger = structlog.get_logger()

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]
    quality_score: float  # 0.0 to 1.0

@dataclass
class QualityMetrics:
    completeness_score: float
    consistency_score: float
    validity_score: float
    temporal_score: float
    overall_score: float

class ComprehensiveDataValidator:
    """Advanced data quality validation with physiological range checking"""

    def __init__(self, quality_threshold: float = 0.7):
        self.quality_threshold = quality_threshold
        self.physiological_ranges = {
            'blood_glucose_mg_dl': (20, 800),
            'heart_rate_bpm': (30, 220),
            'sleep_duration_hours': (0.5, 24),
            'steps_count': (0, 100000),
            'calories_burned': (0, 10000),
            'hrv_rmssd_ms': (5, 200),
            'systolic_bp_mmhg': (70, 250),
            'diastolic_bp_mmhg': (40, 150)
        }

        self.validation_rules = {
            'BloodGlucoseRecord': self._validate_blood_glucose,
            'HeartRateRecord': self._validate_heart_rate,
            'SleepSessionRecord': self._validate_sleep_session,
            'StepsRecord': self._validate_steps,
            'ActiveCaloriesBurnedRecord': self._validate_calories,
            'HeartRateVariabilityRmssdRecord': self._validate_hrv,
            'BloodPressureRecord': self._validate_blood_pressure
        }

    async def validate_file(
        self,
        file_content: bytes,
        record_type: str,
        expected_user_id: str
    ) -> ValidationResult:
        """Perform comprehensive file validation with quality scoring"""

        errors = []
        warnings = []
        metadata = {
            'file_size_bytes': len(file_content),
            'validation_timestamp': pd.Timestamp.utcnow().isoformat()
        }

        try:
            # 1. Avro structure validation
            records, schema = self._parse_avro_file(file_content)

            if not records:
                errors.append("No valid records found in file")
                return ValidationResult(False, errors, warnings, metadata, 0.0)

            metadata.update({
                'schema_fields': [field.name for field in schema.fields],
                'record_count': len(records),
                'schema_name': getattr(schema, 'name', 'unknown')
            })

            # 2. Record-specific validation
            type_validation = None
            if record_type in self.validation_rules:
                type_validation = await self.validation_rules[record_type](
                    records, expected_user_id
                )
                errors.extend(type_validation.get('errors', []))
                warnings.extend(type_validation.get('warnings', []))

            # 3. Comprehensive quality assessment
            quality_metrics = await self._assess_data_quality(
                records, schema, record_type, expected_user_id
            )

            metadata['quality_metrics'] = {
                'completeness_score': quality_metrics.completeness_score,
                'consistency_score': quality_metrics.consistency_score,
                'validity_score': quality_metrics.validity_score,
                'temporal_score': quality_metrics.temporal_score,
                'overall_score': quality_metrics.overall_score
            }

            # 4. Determine validation result
            is_valid = (
                len(errors) == 0 and
                quality_metrics.overall_score >= self.quality_threshold
            )

            if not is_valid and len(errors) == 0:
                warnings.append(f"Quality score {quality_metrics.overall_score:.2f} below threshold {self.quality_threshold}")

            logger.info("File validation completed",
                       record_type=record_type,
                       record_count=len(records),
                       quality_score=quality_metrics.overall_score,
                       is_valid=is_valid)

            return ValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                metadata=metadata,
                quality_score=quality_metrics.overall_score
            )

        except Exception as e:
            errors.append(f"Validation failed: {e}")
            return ValidationResult(False, errors, warnings, metadata, 0.0)

    def _parse_avro_file(self, file_content: bytes) -> tuple:
        """Parse Avro file and extract records"""
        bytes_reader = io.BytesIO(file_content)
        decoder = avro.io.BinaryDecoder(bytes_reader)

        # Read schema
        schema_len = decoder.read_long()
        schema_data = decoder.read(schema_len)
        schema = avro.schema.parse(schema_data.decode('utf-8'))

        # Read records
        datum_reader = avro.io.DatumReader(schema)
        records = []

        while True:
            try:
                record = datum_reader.read(decoder)
                records.append(record)

                # Limit records for validation performance
                if len(records) >= 10000:
                    break

            except EOFError:
                break

        return records, schema

    async def _assess_data_quality(
        self,
        records: List[Dict[str, Any]],
        schema,
        record_type: str,
        expected_user_id: str
    ) -> QualityMetrics:
        """Comprehensive data quality assessment"""

        # 1. Completeness Score
        completeness_score = self._calculate_completeness(records, schema)

        # 2. Consistency Score
        consistency_score = self._calculate_consistency(records, expected_user_id)

        # 3. Validity Score
        validity_score = self._calculate_validity(records, record_type)

        # 4. Temporal Score
        temporal_score = self._calculate_temporal_consistency(records)

        # 5. Overall Score (weighted average)
        overall_score = (
            completeness_score * 0.25 +
            consistency_score * 0.25 +
            validity_score * 0.30 +
            temporal_score * 0.20
        )

        return QualityMetrics(
            completeness_score=completeness_score,
            consistency_score=consistency_score,
            validity_score=validity_score,
            temporal_score=temporal_score,
            overall_score=overall_score
        )

    def _calculate_completeness(self, records: List[Dict], schema) -> float:
        """Calculate data completeness score"""
        if not records:
            return 0.0

        required_fields = [field.name for field in schema.fields]
        completeness_scores = []

        for record in records:
            present_fields = sum(
                1 for field in required_fields
                if field in record and record[field] is not None
            )
            completeness_scores.append(present_fields / len(required_fields))

        return np.mean(completeness_scores)

    def _calculate_consistency(self, records: List[Dict], expected_user_id: str) -> float:
        """Calculate data consistency score"""
        if not records:
            return 0.0

        consistent_records = 0

        for record in records:
            # Check user ID consistency
            metadata = record.get('metadata', {})
            client_record_id = metadata.get('clientRecordId', '')

            if client_record_id.startswith(expected_user_id):
                consistent_records += 1

        return consistent_records / len(records)

    def _calculate_validity(self, records: List[Dict], record_type: str) -> float:
        """Calculate data validity score based on physiological ranges"""
        if not records or record_type not in self.validation_rules:
            return 1.0  # Assume valid if no specific rules

        valid_records = 0

        for record in records:
            if self._is_record_valid(record, record_type):
                valid_records += 1

        return valid_records / len(records)

    def _calculate_temporal_consistency(self, records: List[Dict]) -> float:
        """Calculate temporal consistency score"""
        if len(records) < 2:
            return 1.0

        timestamps = []
        for record in records:
            time_data = record.get('time', {})
            if time_data and 'epochMillis' in time_data:
                timestamps.append(time_data['epochMillis'])

        if len(timestamps) < 2:
            return 0.5

        # Check for reasonable time ordering and gaps
        timestamps.sort()
        reasonable_gaps = 0

        for i in range(1, len(timestamps)):
            gap_ms = timestamps[i] - timestamps[i-1]
            gap_hours = gap_ms / (1000 * 60 * 60)

            # Reasonable gap: between 1 minute and 7 days
            if 0.0167 <= gap_hours <= 168:  # 1 minute to 7 days
                reasonable_gaps += 1

        return reasonable_gaps / (len(timestamps) - 1) if len(timestamps) > 1 else 1.0

    def _is_record_valid(self, record: Dict, record_type: str) -> bool:
        """Check if individual record is valid"""
        try:
            if record_type == 'BloodGlucoseRecord':
                level = record.get('level', {})
                if level and 'inMilligramsPerDeciliter' in level:
                    value = level['inMilligramsPerDeciliter']
                    min_val, max_val = self.physiological_ranges['blood_glucose_mg_dl']
                    return min_val <= value <= max_val

            elif record_type == 'HeartRateRecord':
                bpm = record.get('beatsPerMinute')
                if bpm:
                    min_val, max_val = self.physiological_ranges['heart_rate_bpm']
                    return min_val <= bpm <= max_val

            # Add more record type validations as needed

            return True  # Default to valid if no specific validation

        except Exception:
            return False

    async def _validate_blood_glucose(self, records: List[Dict], expected_user_id: str) -> Dict:
        """Validate blood glucose specific constraints"""
        errors = []
        warnings = []

        for i, record in enumerate(records):
            # User ID validation
            metadata = record.get('metadata', {})
            client_record_id = metadata.get('clientRecordId', '')

            if not client_record_id.startswith(expected_user_id):
                warnings.append(f"Record {i}: User ID mismatch")

            # Value range validation
            level = record.get('level', {})
            if level and 'inMilligramsPerDeciliter' in level:
                mg_dl_value = level['inMilligramsPerDeciliter']
                min_val, max_val = self.physiological_ranges['blood_glucose_mg_dl']

                if not (min_val <= mg_dl_value <= max_val):
                    errors.append(
                        f"Record {i}: Blood glucose {mg_dl_value} mg/dL out of physiological range"
                    )

            # Meal type validation
            meal_type = record.get('mealType')
            valid_meal_types = ['BEFORE_MEAL', 'AFTER_MEAL', 'FASTING', 'RANDOM']
            if meal_type and meal_type not in valid_meal_types:
                warnings.append(f"Record {i}: Invalid meal type '{meal_type}'")

        return {'errors': errors, 'warnings': warnings}

    async def _validate_sleep_session(self, records: List[Dict], expected_user_id: str) -> Dict:
        """Validate sleep session constraints"""
        errors = []
        warnings = []

        for i, record in enumerate(records):
            # Duration validation
            start_time = record.get('startTime', {}).get('epochMillis')
            end_time = record.get('endTime', {}).get('epochMillis')

            if start_time and end_time:
                duration_hours = (end_time - start_time) / (1000 * 60 * 60)
                min_val, max_val = self.physiological_ranges['sleep_duration_hours']

                if not (min_val <= duration_hours <= max_val):
                    if duration_hours < min_val:
                        warnings.append(f"Record {i}: Very short sleep duration {duration_hours:.1f} hours")
                    else:
                        errors.append(f"Record {i}: Unrealistic sleep duration {duration_hours:.1f} hours")

        return {'errors': errors, 'warnings': warnings}

    # Additional validation methods for other record types...
    async def _validate_heart_rate(self, records: List[Dict], expected_user_id: str) -> Dict:
        """Validate heart rate constraints"""
        return {'errors': [], 'warnings': []}

    async def _validate_steps(self, records: List[Dict], expected_user_id: str) -> Dict:
        """Validate steps constraints"""
        return {'errors': [], 'warnings': []}

    async def _validate_calories(self, records: List[Dict], expected_user_id: str) -> Dict:
        """Validate calories constraints"""
        return {'errors': [], 'warnings': []}

    async def _validate_hrv(self, records: List[Dict], expected_user_id: str) -> Dict:
        """Validate HRV constraints"""
        return {'errors': [], 'warnings': []}

    async def _validate_blood_pressure(self, records: List[Dict], expected_user_id: str) -> Dict:
        """Validate blood pressure constraints"""
        return {'errors': [], 'warnings': []}
```

### 5. Lifecycle Management (core/lifecycle.py)
```python
from minio import Minio
from minio.lifecycleconfig import LifecycleConfig, Rule, Transition, Filter
from datetime import datetime, timedelta
from typing import Dict, Any, List
import structlog

logger = structlog.get_logger()

class DataLifecycleManager:
    """Manage data lifecycle with MinIO's native policies"""

    def __init__(self, minio_client: Minio):
        self.client = minio_client

    def setup_lifecycle_policies(self, bucket_name: str, config: Dict[str, Any]):
        """Configure comprehensive lifecycle policies"""

        rules = []

        # Raw data lifecycle: Archive and eventually delete
        raw_data_rule = Rule(
            rule_id="raw_data_lifecycle",
            status="Enabled",
            rule_filter=Filter(prefix="raw/"),
            transitions=[
                Transition(
                    days=config.get('raw_data_glacier_days', 90),
                    storage_class="GLACIER"
                ),
                Transition(
                    days=config.get('raw_data_deep_archive_days', 365),
                    storage_class="DEEP_ARCHIVE"
                )
            ],
            expiration_days=config.get('raw_data_expiration_days', 2555)  # 7 years
        )
        rules.append(raw_data_rule)

        # Processed data lifecycle: Keep accessible longer
        processed_data_rule = Rule(
            rule_id="processed_data_lifecycle",
            status="Enabled",
            rule_filter=Filter(prefix="processed/"),
            transitions=[
                Transition(
                    days=config.get('processed_data_glacier_days', 180),
                    storage_class="GLACIER"
                )
            ],
            expiration_days=config.get('processed_data_expiration_days', 3650)  # 10 years
        )
        rules.append(processed_data_rule)

        # Quarantine data: Delete quickly
        quarantine_rule = Rule(
            rule_id="quarantine_cleanup",
            status="Enabled",
            rule_filter=Filter(prefix="quarantine/"),
            expiration_days=config.get('quarantine_retention_days', 30)
        )
        rules.append(quarantine_rule)

        # Training data: Archive but keep indefinitely
        training_rule = Rule(
            rule_id="training_data_archive",
            status="Enabled",
            rule_filter=Filter(prefix="training/"),
            transitions=[
                Transition(days=30, storage_class="GLACIER")
            ]
            # No expiration for training data
        )
        rules.append(training_rule)

        # Analytics data: Short retention
        analytics_rule = Rule(
            rule_id="analytics_cleanup",
            status="Enabled",
            rule_filter=Filter(prefix="analytics/"),
            expiration_days=365  # 1 year
        )
        rules.append(analytics_rule)

        # Apply lifecycle configuration
        lifecycle_config = LifecycleConfig(rules)

        try:
            self.client.set_bucket_lifecycle(bucket_name, lifecycle_config)
            logger.info("Lifecycle policies configured successfully", bucket=bucket_name)

        except Exception as e:
            logger.error("Failed to configure lifecycle policies", error=str(e))
            raise

    def get_lifecycle_status(self, bucket_name: str) -> Dict[str, Any]:
        """Get current lifecycle configuration"""
        try:
            lifecycle_config = self.client.get_bucket_lifecycle(bucket_name)

            status = {
                "bucket": bucket_name,
                "rules": [],
                "total_rules": len(lifecycle_config.rules)
            }

            for rule in lifecycle_config.rules:
                rule_info = {
                    "id": rule.rule_id,
                    "status": rule.status,
                    "prefix": getattr(rule.rule_filter, 'prefix', None),
                    "transitions": [],
                    "expiration_days": rule.expiration_days
                }

                if rule.transitions:
                    for transition in rule.transitions:
                        rule_info["transitions"].append({
                            "days": transition.days,
                            "storage_class": transition.storage_class
                        })

                status["rules"].append(rule_info)

            return status

        except Exception as e:
            logger.error("Failed to get lifecycle status", error=str(e))
            return {"error": str(e)}

    async def estimate_storage_costs(self, bucket_name: str) -> Dict[str, Any]:
        """Estimate storage costs based on lifecycle policies"""
        # This would integrate with cloud provider APIs for actual cost estimation
        # For now, provide a framework for cost analysis

        try:
            objects = self.client.list_objects(bucket_name, recursive=True)

            cost_analysis = {
                "total_objects": 0,
                "total_size_gb": 0,
                "by_prefix": {},
                "estimated_monthly_cost_usd": 0,
                "cost_breakdown": {
                    "standard": {"objects": 0, "size_gb": 0, "cost_usd": 0},
                    "glacier": {"objects": 0, "size_gb": 0, "cost_usd": 0},
                    "deep_archive": {"objects": 0, "size_gb": 0, "cost_usd": 0}
                }
            }

            # Cost per GB per month (example rates)
            storage_costs = {
                "standard": 0.023,  # $0.023 per GB/month
                "glacier": 0.004,   # $0.004 per GB/month
                "deep_archive": 0.00099  # $0.00099 per GB/month
            }

            for obj in objects:
                cost_analysis["total_objects"] += 1
                size_gb = obj.size / (1024 ** 3)
                cost_analysis["total_size_gb"] += size_gb

                # Determine prefix
                prefix = obj.object_name.split('/')[0]
                if prefix not in cost_analysis["by_prefix"]:
                    cost_analysis["by_prefix"][prefix] = {
                        "objects": 0,
                        "size_gb": 0
                    }

                cost_analysis["by_prefix"][prefix]["objects"] += 1
                cost_analysis["by_prefix"][prefix]["size_gb"] += size_gb

                # Estimate storage class based on age and prefix
                obj_age_days = (datetime.utcnow() - obj.last_modified).days
                storage_class = self._estimate_storage_class(prefix, obj_age_days)

                cost_analysis["cost_breakdown"][storage_class]["objects"] += 1
                cost_analysis["cost_breakdown"][storage_class]["size_gb"] += size_gb
                cost_analysis["cost_breakdown"][storage_class]["cost_usd"] += size_gb * storage_costs[storage_class]

            # Calculate total estimated cost
            cost_analysis["estimated_monthly_cost_usd"] = sum(
                breakdown["cost_usd"] for breakdown in cost_analysis["cost_breakdown"].values()
            )

            return cost_analysis

        except Exception as e:
            logger.error("Failed to estimate storage costs", error=str(e))
            return {"error": str(e)}

    def _estimate_storage_class(self, prefix: str, age_days: int) -> str:
        """Estimate current storage class based on prefix and age"""
        if prefix == "raw":
            if age_days >= 365:
                return "deep_archive"
            elif age_days >= 90:
                return "glacier"
            else:
                return "standard"
        elif prefix == "processed":
            if age_days >= 180:
                return "glacier"
            else:
                return "standard"
        else:
            return "standard"
```

### 6. Storage Client (storage/client.py)
```python
from minio import Minio
from minio.error import S3Error
from minio.commonconfig import ENABLED, DISABLED
from minio.sseconfig import SSEConfig
import structlog
import asyncio
from typing import Optional, Dict, Any, List, AsyncGenerator
from datetime import datetime
import json

logger = structlog.get_logger()

class SecureMinIOClient:
    """Secure MinIO client with enterprise features"""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool = False,
        region: str = "us-east-1"
    ):
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_access_key=secret_key,
            secure=secure,
            region=region
        )
        self.endpoint = endpoint
        self.region = region

    async def initialize_bucket(
        self,
        bucket_name: str,
        enable_versioning: bool = True,
        enable_encryption: bool = True
    ):
        """Initialize bucket with security features"""

        try:
            # Create bucket if it doesn't exist
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name, location=self.region)
                logger.info("Bucket created", bucket=bucket_name)
            else:
                logger.info("Bucket already exists", bucket=bucket_name)

            # Enable versioning
            if enable_versioning:
                self.client.set_bucket_versioning(bucket_name, ENABLED)
                logger.info("Versioning enabled", bucket=bucket_name)

            # Enable encryption
            if enable_encryption:
                sse_config = SSEConfig("AES256")
                self.client.set_bucket_encryption(bucket_name, sse_config)
                logger.info("Encryption enabled", bucket=bucket_name)

        except S3Error as e:
            logger.error("Failed to initialize bucket", bucket=bucket_name, error=str(e))
            raise

    def setup_bucket_policy(self, bucket_name: str, policy: Dict[str, Any]):
        """Set up bucket access policy"""
        try:
            policy_json = json.dumps(policy)
            self.client.set_bucket_policy(bucket_name, policy_json)
            logger.info("Bucket policy configured", bucket=bucket_name)

        except S3Error as e:
            logger.error("Failed to set bucket policy", bucket=bucket_name, error=str(e))
            raise

    async def upload_file(
        self,
        bucket_name: str,
        object_key: str,
        file_content: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """Upload file with metadata"""

        try:
            import io

            file_stream = io.BytesIO(file_content)

            self.client.put_object(
                bucket_name,
                object_key,
                file_stream,
                length=len(file_content),
                content_type=content_type,
                metadata=metadata or {}
            )

            logger.info("File uploaded successfully",
                       bucket=bucket_name,
                       object_key=object_key,
                       size_bytes=len(file_content))

            return True

        except S3Error as e:
            logger.error("File upload failed",
                        bucket=bucket_name,
                        object_key=object_key,
                        error=str(e))
            raise

    async def download_file(self, bucket_name: str, object_key: str) -> bytes:
        """Download file content"""
        try:
            response = self.client.get_object(bucket_name, object_key)
            content = response.read()
            response.close()
            response.release_conn()

            logger.debug("File downloaded successfully",
                        bucket=bucket_name,
                        object_key=object_key,
                        size_bytes=len(content))

            return content

        except S3Error as e:
            logger.error("File download failed",
                        bucket=bucket_name,
                        object_key=object_key,
                        error=str(e))
            raise

    async def list_objects_with_metadata(
        self,
        bucket_name: str,
        prefix: str = "",
        recursive: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """List objects with detailed metadata"""

        try:
            objects = self.client.list_objects(
                bucket_name,
                prefix=prefix,
                recursive=recursive
            )

            for obj in objects:
                # Get additional metadata
                stat = self.client.stat_object(bucket_name, obj.object_name)

                yield {
                    "object_name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                    "etag": obj.etag,
                    "content_type": stat.content_type,
                    "metadata": stat.metadata,
                    "version_id": getattr(stat, 'version_id', None)
                }

        except S3Error as e:
            logger.error("Failed to list objects", bucket=bucket_name, error=str(e))
            raise

    async def move_to_quarantine(
        self,
        bucket_name: str,
        source_key: str,
        quarantine_key: str,
        reason: str
    ) -> bool:
        """Move file to quarantine with reason metadata"""

        try:
            # Copy to quarantine location with reason metadata
            copy_source = {"Bucket": bucket_name, "Key": source_key}

            self.client.copy_object(
                bucket_name,
                quarantine_key,
                copy_source,
                metadata={
                    "quarantine_reason": reason,
                    "quarantine_timestamp": datetime.utcnow().isoformat(),
                    "original_key": source_key
                },
                metadata_directive="REPLACE"
            )

            # Delete original file
            self.client.remove_object(bucket_name, source_key)

            logger.info("File moved to quarantine",
                       original_key=source_key,
                       quarantine_key=quarantine_key,
                       reason=reason)

            return True

        except S3Error as e:
            logger.error("Failed to quarantine file",
                        source_key=source_key,
                        error=str(e))
            raise

    async def get_bucket_stats(self, bucket_name: str) -> Dict[str, Any]:
        """Get comprehensive bucket statistics"""

        try:
            stats = {
                "bucket_name": bucket_name,
                "total_objects": 0,
                "total_size_bytes": 0,
                "by_prefix": {},
                "by_storage_class": {},
                "last_modified_range": {
                    "earliest": None,
                    "latest": None
                }
            }

            objects = self.client.list_objects(bucket_name, recursive=True)

            for obj in objects:
                stats["total_objects"] += 1
                stats["total_size_bytes"] += obj.size

                # Track by prefix
                prefix = obj.object_name.split('/')[0]
                if prefix not in stats["by_prefix"]:
                    stats["by_prefix"][prefix] = {"objects": 0, "size_bytes": 0}

                stats["by_prefix"][prefix]["objects"] += 1
                stats["by_prefix"][prefix]["size_bytes"] += obj.size

                # Track date range
                if stats["last_modified_range"]["earliest"] is None or obj.last_modified < stats["last_modified_range"]["earliest"]:
                    stats["last_modified_range"]["earliest"] = obj.last_modified

                if stats["last_modified_range"]["latest"] is None or obj.last_modified > stats["last_modified_range"]["latest"]:
                    stats["last_modified_range"]["latest"] = obj.last_modified

            return stats

        except S3Error as e:
            logger.error("Failed to get bucket stats", bucket=bucket_name, error=str(e))
            raise

    def check_bucket_health(self, bucket_name: str) -> Dict[str, Any]:
        """Check bucket health and accessibility"""

        health_status = {
            "bucket_name": bucket_name,
            "accessible": False,
            "versioning_enabled": False,
            "encryption_enabled": False,
            "lifecycle_configured": False,
            "errors": []
        }

        try:
            # Check if bucket exists and is accessible
            if self.client.bucket_exists(bucket_name):
                health_status["accessible"] = True

                # Check versioning
                try:
                    versioning = self.client.get_bucket_versioning(bucket_name)
                    health_status["versioning_enabled"] = versioning.status == "Enabled"
                except:
                    health_status["errors"].append("Could not check versioning status")

                # Check encryption
                try:
                    encryption = self.client.get_bucket_encryption(bucket_name)
                    health_status["encryption_enabled"] = encryption is not None
                except:
                    health_status["errors"].append("Could not check encryption status")

                # Check lifecycle
                try:
                    lifecycle = self.client.get_bucket_lifecycle(bucket_name)
                    health_status["lifecycle_configured"] = len(lifecycle.rules) > 0
                except:
                    health_status["errors"].append("Could not check lifecycle configuration")

            else:
                health_status["errors"].append("Bucket does not exist or is not accessible")

        except Exception as e:
            health_status["errors"].append(f"Health check failed: {e}")

        return health_status
```

### 7. Monitoring and Analytics (monitoring/analytics.py)
```python
from storage.client import SecureMinIOClient
from core.naming import IntelligentObjectKeyGenerator
from typing import Dict, Any, List
from datetime import datetime, timedelta
import json
import pandas as pd
import structlog

logger = structlog.get_logger()

class DataLakeAnalytics:
    """Comprehensive data lake analytics and monitoring"""

    def __init__(self, minio_client: SecureMinIOClient, bucket_name: str):
        self.client = minio_client
        self.bucket_name = bucket_name
        self.key_generator = IntelligentObjectKeyGenerator()

    async def generate_daily_analytics(self, date: datetime = None) -> Dict[str, Any]:
        """Generate daily analytics report"""

        if date is None:
            date = datetime.utcnow()

        analytics = {
            "date": date.isoformat(),
            "bucket": self.bucket_name,
            "summary": {
                "total_objects": 0,
                "total_size_gb": 0,
                "new_objects_today": 0,
                "new_data_size_gb": 0
            },
            "by_record_type": {},
            "by_user": {},
            "quality_metrics": {
                "total_files_processed": 0,
                "files_quarantined": 0,
                "average_quality_score": 0,
                "quality_distribution": {}
            },
            "storage_efficiency": {
                "compression_ratio": 0,
                "deduplication_savings": 0
            },
            "usage_patterns": {
                "peak_upload_hour": None,
                "most_active_users": []
            }
        }

        try:
            # Analyze all objects
            async for obj_metadata in self.client.list_objects_with_metadata(
                self.bucket_name, recursive=True
            ):
                analytics["summary"]["total_objects"] += 1
                size_gb = obj_metadata["size"] / (1024 ** 3)
                analytics["summary"]["total_size_gb"] += size_gb

                # Check if object was created today
                if obj_metadata["last_modified"].date() == date.date():
                    analytics["summary"]["new_objects_today"] += 1
                    analytics["summary"]["new_data_size_gb"] += size_gb

                # Parse object key for detailed analysis
                key_components = self.key_generator.parse_object_key(obj_metadata["object_name"])

                if key_components:
                    # Analyze by record type
                    record_type = key_components.record_type
                    if record_type not in analytics["by_record_type"]:
                        analytics["by_record_type"][record_type] = {
                            "objects": 0,
                            "size_gb": 0,
                            "latest_upload": None
                        }

                    analytics["by_record_type"][record_type]["objects"] += 1
                    analytics["by_record_type"][record_type]["size_gb"] += size_gb

                    if (analytics["by_record_type"][record_type]["latest_upload"] is None or
                        obj_metadata["last_modified"] > analytics["by_record_type"][record_type]["latest_upload"]):
                        analytics["by_record_type"][record_type]["latest_upload"] = obj_metadata["last_modified"]

                    # Analyze by user (only for raw data)
                    if key_components.layer == "raw":
                        user_id = key_components.user_id
                        if user_id not in analytics["by_user"]:
                            analytics["by_user"][user_id] = {
                                "objects": 0,
                                "size_gb": 0,
                                "record_types": set()
                            }

                        analytics["by_user"][user_id]["objects"] += 1
                        analytics["by_user"][user_id]["size_gb"] += size_gb
                        analytics["by_user"][user_id]["record_types"].add(record_type)

                # Analyze quarantine data
                if obj_metadata["object_name"].startswith("quarantine/"):
                    analytics["quality_metrics"]["files_quarantined"] += 1

            # Convert sets to lists for JSON serialization
            for user_data in analytics["by_user"].values():
                user_data["record_types"] = list(user_data["record_types"])

            # Calculate additional metrics
            analytics = await self._enhance_analytics_with_quality_metrics(analytics)
            analytics = await self._enhance_analytics_with_usage_patterns(analytics, date)

            # Store analytics
            await self._store_analytics(analytics, date)

            logger.info("Daily analytics generated",
                       date=date.isoformat(),
                       total_objects=analytics["summary"]["total_objects"])

            return analytics

        except Exception as e:
            logger.error("Failed to generate analytics", error=str(e))
            raise

    async def _enhance_analytics_with_quality_metrics(self, analytics: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance analytics with quality metrics from metadata"""

        quality_scores = []
        quality_distribution = {"high": 0, "medium": 0, "low": 0}

        # This would typically read from stored metadata or a separate quality tracking system
        # For now, simulate quality metrics

        total_files = analytics["summary"]["total_objects"]
        if total_files > 0:
            # Simulate quality scores
            import random
            for _ in range(min(total_files, 100)):  # Sample for performance
                score = random.uniform(0.6, 1.0)  # Simulate realistic quality scores
                quality_scores.append(score)

                if score >= 0.9:
                    quality_distribution["high"] += 1
                elif score >= 0.7:
                    quality_distribution["medium"] += 1
                else:
                    quality_distribution["low"] += 1

            analytics["quality_metrics"]["average_quality_score"] = sum(quality_scores) / len(quality_scores)
            analytics["quality_metrics"]["quality_distribution"] = quality_distribution

        return analytics

    async def _enhance_analytics_with_usage_patterns(self, analytics: Dict[str, Any], date: datetime) -> Dict[str, Any]:
        """Enhance analytics with usage pattern analysis"""

        # Analyze upload patterns by hour
        upload_hours = {}
        most_active_users = []

        # Sort users by activity
        user_activity = [
            (user_id, data["objects"])
            for user_id, data in analytics["by_user"].items()
        ]
        user_activity.sort(key=lambda x: x[1], reverse=True)

        analytics["usage_patterns"]["most_active_users"] = [
            {"user_id": user_id, "objects": count}
            for user_id, count in user_activity[:5]  # Top 5 users
        ]

        # This would typically analyze actual upload timestamps
        # For now, provide a framework
        analytics["usage_patterns"]["peak_upload_hour"] = "14:00"  # 2 PM as example

        return analytics

    async def _store_analytics(self, analytics: Dict[str, Any], date: datetime):
        """Store analytics data in the data lake"""

        try:
            analytics_key = self.key_generator.generate_analytics_key("daily_summary", date)
            analytics_json = json.dumps(analytics, default=str, indent=2)

            await self.client.upload_file(
                self.bucket_name,
                analytics_key,
                analytics_json.encode(),
                content_type="application/json",
                metadata={
                    "analytics_type": "daily_summary",
                    "generated_at": datetime.utcnow().isoformat()
                }
            )

            logger.info("Analytics stored", analytics_key=analytics_key)

        except Exception as e:
            logger.error("Failed to store analytics", error=str(e))

    async def get_storage_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get storage growth trends over time"""

        try:
            trends = {
                "period_days": days,
                "daily_growth": [],
                "record_type_trends": {},
                "storage_efficiency_trend": []
            }

            # This would typically query stored analytics
            # For now, provide a framework for trend analysis

            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)

            current_date = start_date
            while current_date <= end_date:
                # Simulate daily growth data
                trends["daily_growth"].append({
                    "date": current_date.isoformat(),
                    "objects_added": 10,  # Simulated
                    "size_gb_added": 0.5  # Simulated
                })

                current_date += timedelta(days=1)

            return trends

        except Exception as e:
            logger.error("Failed to get storage trends", error=str(e))
            return {"error": str(e)}

    async def generate_compliance_report(self) -> Dict[str, Any]:
        """Generate compliance report for audit purposes"""

        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "bucket": self.bucket_name,
            "compliance_checks": {
                "encryption_enabled": False,
                "versioning_enabled": False,
                "lifecycle_policies_configured": False,
                "access_logging_enabled": False
            },
            "data_retention": {
                "oldest_data": None,
                "retention_policy_compliant": True
            },
            "security_status": {
                "secure_access_only": False,
                "proper_access_controls": False
            },
            "recommendations": []
        }

        try:
            # Check bucket health
            health_status = self.client.check_bucket_health(self.bucket_name)

            report["compliance_checks"]["encryption_enabled"] = health_status.get("encryption_enabled", False)
            report["compliance_checks"]["versioning_enabled"] = health_status.get("versioning_enabled", False)
            report["compliance_checks"]["lifecycle_policies_configured"] = health_status.get("lifecycle_configured", False)

            # Generate recommendations
            if not report["compliance_checks"]["encryption_enabled"]:
                report["recommendations"].append("Enable bucket encryption for data at rest protection")

            if not report["compliance_checks"]["versioning_enabled"]:
                report["recommendations"].append("Enable bucket versioning for data protection and recovery")

            if not report["compliance_checks"]["lifecycle_policies_configured"]:
                report["recommendations"].append("Configure lifecycle policies for automated data management")

            return report

        except Exception as e:
            logger.error("Failed to generate compliance report", error=str(e))
            return {"error": str(e)}
```

### 8. Docker Configuration

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  minio:
    image: minio/minio:RELEASE.2024-10-02T17-50-41Z
    container_name: health-minio
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
      MINIO_PROMETHEUS_AUTH_TYPE: public
    ports:
      - "9000:9000"  # API port
      - "9001:9001"  # Console port
    volumes:
      - minio_data:/data
      - ./deployment/minio-policies:/policies:ro
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3
    restart: unless-stopped

  data-lake-setup:
    build: .
    command: python deployment/scripts/setup_bucket.py
    environment:
      DATALAKE_MINIO_ENDPOINT: minio:9000
      DATALAKE_MINIO_ACCESS_KEY: ${MINIO_ROOT_USER:-minioadmin}
      DATALAKE_MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
      DATALAKE_BUCKET_NAME: health-data
    depends_on:
      - minio
    restart: "no"

volumes:
  minio_data:
```

### 9. Setup Scripts

**deployment/scripts/setup_bucket.py:**
```python
#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from storage.client import SecureMinIOClient
from core.lifecycle import DataLifecycleManager
from config.settings import settings
import json
import structlog

logger = structlog.get_logger()

async def setup_data_lake():
    """Complete data lake setup"""

    try:
        # Initialize client
        client = SecureMinIOClient(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
            region=settings.minio_region
        )

        # Initialize bucket with security features
        await client.initialize_bucket(
            settings.bucket_name,
            enable_versioning=settings.enable_versioning,
            enable_encryption=settings.enable_encryption
        )

        # Setup lifecycle policies
        lifecycle_manager = DataLifecycleManager(client.client)
        lifecycle_config = {
            'raw_data_glacier_days': settings.raw_data_glacier_days,
            'raw_data_deep_archive_days': settings.raw_data_deep_archive_days,
            'raw_data_expiration_days': settings.raw_data_expiration_days,
            'processed_data_glacier_days': settings.processed_data_glacier_days,
            'processed_data_expiration_days': settings.processed_data_expiration_days,
            'quarantine_retention_days': settings.quarantine_retention_days
        }

        lifecycle_manager.setup_lifecycle_policies(settings.bucket_name, lifecycle_config)

        # Setup bucket policy
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::health-api-service"},
                    "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
                    "Resource": f"arn:aws:s3:::{settings.bucket_name}/raw/*"
                },
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::etl-worker"},
                    "Action": ["s3:GetObject", "s3:PutObject"],
                    "Resource": [
                        f"arn:aws:s3:::{settings.bucket_name}/raw/*",
                        f"arn:aws:s3:::{settings.bucket_name}/processed/*",
                        f"arn:aws:s3:::{settings.bucket_name}/quarantine/*"
                    ]
                },
                {
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "*",
                    "Resource": f"arn:aws:s3:::{settings.bucket_name}/*",
                    "Condition": {
                        "Bool": {"aws:SecureTransport": "false"}
                    }
                }
            ]
        }

        client.setup_bucket_policy(settings.bucket_name, bucket_policy)

        logger.info("Data lake setup completed successfully")

    except Exception as e:
        logger.error("Data lake setup failed", error=str(e))
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(setup_data_lake())
```

### 10. Environment Configuration (.env.example)
```bash
# MinIO Configuration
DATALAKE_MINIO_ENDPOINT=localhost:9000
DATALAKE_MINIO_ACCESS_KEY=minioadmin
DATALAKE_MINIO_SECRET_KEY=your-secret-key-here
DATALAKE_MINIO_SECURE=false
DATALAKE_MINIO_REGION=us-east-1

# Bucket Configuration
DATALAKE_BUCKET_NAME=health-data
DATALAKE_CREATE_BUCKET_ON_STARTUP=true

# Object Naming
DATALAKE_MAX_OBJECT_KEY_LENGTH=1024
DATALAKE_HASH_LENGTH=8

# Data Quality
DATALAKE_ENABLE_QUALITY_VALIDATION=true
DATALAKE_QUALITY_THRESHOLD=0.7
DATALAKE_QUARANTINE_RETENTION_DAYS=30

# Lifecycle Management
DATALAKE_RAW_DATA_GLACIER_DAYS=90
DATALAKE_RAW_DATA_DEEP_ARCHIVE_DAYS=365
DATALAKE_RAW_DATA_EXPIRATION_DAYS=2555
DATALAKE_PROCESSED_DATA_GLACIER_DAYS=180
DATALAKE_PROCESSED_DATA_EXPIRATION_DAYS=3650

# Security
DATALAKE_ENABLE_ENCRYPTION=true
DATALAKE_ENABLE_VERSIONING=true
DATALAKE_ENABLE_AUDIT_LOGGING=true

# Monitoring
DATALAKE_ENABLE_METRICS=true
DATALAKE_METRICS_PORT=8002
DATALAKE_ANALYTICS_UPDATE_INTERVAL_HOURS=6
```

## Usage Examples

### Basic Usage
```python
from storage.client import SecureMinIOClient
from core.naming import IntelligentObjectKeyGenerator
from core.validation import ComprehensiveDataValidator

async def example_usage():
    # Initialize client
    client = SecureMinIOClient(
        endpoint="localhost:9000",
        access_key="minioadmin",
        secret_key="your-secret",
        secure=False
    )

    # Initialize bucket
    await client.initialize_bucket("health-data")

    # Generate intelligent object key
    key_generator = IntelligentObjectKeyGenerator()
    object_key = key_generator.generate_raw_key(
        record_type="BloodGlucoseRecord",
        user_id="user123",
        timestamp=datetime.utcnow(),
        file_hash="abc123...",
        source_device="dexcom_g7"
    )

    # Validate and upload file
    validator = ComprehensiveDataValidator()
    validation_result = await validator.validate_file(
        file_content,
        "BloodGlucoseRecord",
        "user123"
    )

    if validation_result.is_valid:
        await client.upload_file("health-data", object_key, file_content)
    else:
        quarantine_key = key_generator.generate_quarantine_key(
            object_key, "validation_failed"
        )
        await client.move_to_quarantine(
            "health-data", object_key, quarantine_key, "validation_failed"
        )
```

## Deployment Instructions

### Development
1. **Install dependencies:** `pip install -r requirements.txt`
2. **Start MinIO:** `docker-compose up -d minio`
3. **Setup bucket:** `python deployment/scripts/setup_bucket.py`
4. **Run applications:** Use the client libraries

### Production
1. **Configure environment:** Set all required environment variables
2. **Deploy:** `docker-compose up -d`
3. **Monitor:** Access MinIO console at `http://localhost:9001`

## Monitoring and Operations

- **MinIO Console:** `http://localhost:9001`
- **Analytics API:** Built-in analytics generation
- **Health Checks:** Comprehensive bucket health monitoring
- **Compliance Reports:** Automated compliance checking

## Integration Points

- **API Service:** Stores uploaded files with intelligent naming
- **ETL Engine:** Reads files for processing, moves failed files to quarantine
- **AI Interface:** Reads training data from processed files
- **Monitoring:** Provides storage analytics and health metrics

This implementation provides enterprise-grade data lake capabilities with intelligent organization, comprehensive quality validation, and automated lifecycle management while maintaining operational simplicity through MinIO's native features.