# ETL Narrative Engine - Implementation Specification v3.0

**Document Version:** 3.0 (Merged Edition)
**Created:** 2025-11-15
**Status:** Ready for Implementation
**Authors:** Merged from v1.0 and v2.0 specifications

---

## Executive Summary

The ETL Narrative Engine is a critical microservice that transforms raw health data from Android Health Connect (in Apache Avro format) into clinically meaningful narratives and structured training data for AI model development. This service consumes messages from RabbitMQ, processes health data files from the MinIO data lake, applies clinical domain expertise, and generates high-quality training datasets in JSONL format.

### Key Objectives

1. **Process Health Data**: Consume messages from RabbitMQ, download Avro files from MinIO, and extract health records
2. **Generate Clinical Narratives**: Transform raw health metrics into human-readable, clinically accurate insights
3. **Produce Training Data**: Output JSONL format data with instruction-response pairs for AI model fine-tuning
4. **Ensure Idempotency**: Prevent duplicate processing using persistent deduplication
5. **Enable Local Development**: Support full development and testing using existing sample Avro files
6. **Production Ready**: Include comprehensive monitoring, security, and operational considerations

### Key Design Decisions

- ✅ **Local-First Development**: Use 26 existing sample Avro files for complete local development
- ✅ **Dual Deduplication**: SQLite for single instance, Redis for distributed deployment
- ✅ **Clinical Accuracy**: Specialized processors with domain-specific algorithms
- ✅ **Comprehensive Observability**: Prometheus metrics, structured logging, Jaeger tracing
- ✅ **Intelligent Error Handling**: Classification-based retry logic with quarantine mechanism

---

## 1. System Architecture

### 1.1 Service Position in Platform

```
┌─────────────────────────────────────────────────────────────────┐
│  WebAuthn Stack (separate)                                      │
│  - Envoy Gateway (port 8000)                                    │
│  - Jaeger (port 16687) - Shared distributed tracing             │
└─────────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  Health Services Stack                                          │
│                                                                 │
│  ┌─────────────┐     ┌──────────────┐     ┌─────────────────┐ │
│  │ Health API  │────▶│ Message Queue│────▶│ ETL Narrative   │ │
│  │ Service     │     │ (RabbitMQ)   │     │ Engine          │ │
│  └─────────────┘     └──────────────┘     └────────┬────────┘ │
│                                                     │          │
│                                                     ▼          │
│                                            ┌─────────────────┐ │
│                                            │ Data Lake       │ │
│                                            │ (MinIO)         │ │
│                                            │                 │ │
│                                            │ - Read: raw/    │ │
│                                            │ - Write:        │ │
│                                            │   training/     │ │
│                                            │   quarantine/   │ │
│                                            └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Message Receipt                                              │
│    - Receive HealthDataMessage from RabbitMQ                    │
│    - Extract correlation_id, idempotency_key                    │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Deduplication Check                                          │
│    - Query SQLite/Redis deduplication store                     │
│    - If already processed: ACK message, skip processing         │
│    - Else: Mark as "processing_started" in store                │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. File Download                                                │
│    - Download Avro file from MinIO using bucket + key           │
│    - Stream to memory or temp file                              │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Data Validation                                              │
│    - Validate Avro schema                                       │
│    - Check physiological ranges                                 │
│    - Assess data quality score                                  │
│    - If quality < threshold: Move to quarantine, ACK message    │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Record Extraction                                            │
│    - Parse Avro file using fastavro                             │
│    - Extract records into Python dictionaries                   │
│    - Convert to pandas DataFrame for analysis                   │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. Clinical Processing                                          │
│    - Select processor based on record_type                      │
│    - Calculate statistical insights (mean, std, percentiles)    │
│    - Extract temporal patterns (time of day, day of week)       │
│    - Apply clinical domain knowledge                            │
│    - Generate clinical assessment (control quality, risk)       │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. Narrative Generation                                         │
│    - Format clinical insights into human-readable narrative     │
│    - Include recommendations based on findings                  │
│    - Generate contextual instruction for training data          │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. Training Data Output                                         │
│    - Create JSONL entry with instruction + output + metadata    │
│    - Upload to MinIO: training/{category}/{YYYY}/{MM}/{file}    │
│    - Include full lineage and quality metrics                   │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. Completion                                                   │
│    - Mark as "completed" in deduplication store                 │
│    - ACK RabbitMQ message                                       │
│    - Record processing metrics (duration, records, quality)     │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Integration Points

| Service | Purpose | Protocol | Connection Details |
|---------|---------|----------|--------------------|
| **RabbitMQ** | Message consumption | AMQP | Queue: `health_data_processing`<br>Exchange: `health_data_exchange`<br>Prefetch: 1 |
| **MinIO (Data Lake)** | File storage | S3 API | Bucket: `health-data`<br>Read: `raw/`<br>Write: `training/`, `quarantine/` |
| **SQLite/Redis** | Deduplication | File/Redis Protocol | SQLite: `/data/etl_processed_messages.db`<br>Redis: Database 2 |
| **Prometheus** | Metrics export | HTTP | Port: 8004 (configurable) |
| **Jaeger** | Distributed tracing | OTLP/gRPC | Shared from webauthn-stack:<br>`http://localhost:4319` |

---

## 2. Development Strategy

### 2.1 Local-First Development Approach

**CRITICAL DECISION**: The ETL Narrative Engine will be developed and tested **entirely locally** using existing sample Avro files. This eliminates the need for cloud deployment during development.

**Rationale:**
1. ✅ 26 sample Avro files already exist in `docs/sample-avro-files/`
2. ✅ All infrastructure runs locally via Docker (MinIO, RabbitMQ, PostgreSQL, Redis)
3. ✅ Health API service can upload sample files to local MinIO
4. ✅ Integration tests can verify full end-to-end processing
5. ✅ No cloud costs or deployment complexity during development

### 2.2 Sample Data Inventory

Based on `docs/sample-avro-files/`:

| Record Type | Files | File Size Range | Estimated Records | Priority |
|-------------|-------|-----------------|-------------------|----------|
| **BloodGlucoseRecord** | 5 | 38KB - 39KB | ~200-300 each | HIGH |
| **HeartRateRecord** | 5 | 13KB - 15KB | ~100-150 each | HIGH |
| **SleepSessionRecord** | 5 | 2.5KB - 4KB | ~3-5 sessions | MEDIUM |
| **StepsRecord** | 5 | 1.2KB - 1.4KB | ~5-10 each | MEDIUM |
| **ActiveCaloriesBurnedRecord** | 3 | ~1.3KB | ~5-10 each | LOW |
| **HeartRateVariabilityRmssdRecord** | 3 | ~13KB | ~100 each | MEDIUM |

**Total Sample Dataset:**
- 26 files
- ~200KB total size
- Covers all 6 supported health data types
- Sufficient for comprehensive local development and testing

**Note:** The Health API uses `Avro` prefix (e.g., `AvroBloodGlucoseRecord`), but data lake and message queue use the base name (e.g., `BloodGlucoseRecord`).

### 2.3 Development Workflow

```bash
# Phase 1: Local Development Setup
1. Start local infrastructure:
   docker compose up -d minio rabbitmq postgres redis

2. Load sample data into MinIO:
   # Option A: Via Health API (end-to-end testing)
   python scripts/upload_to_health_api.py

   # Option B: Direct injection (rapid iteration)
   python scripts/load_sample_data.py --mode direct --all

3. Develop ETL processors:
   - Implement message consumer
   - Build clinical processors for each record type
   - Generate narratives and training data

4. Test with sample data:
   - Integration tests verify processing of all sample files
   - Validate narrative quality and training data format

# Phase 2: Production Deployment (Future)
5. Deploy to cloud when Android app is ready:
   - Container deployment (AWS ECS, GCP Cloud Run, Azure Container Instances)
   - Connect to cloud-hosted infrastructure
   - Real Android app uploads flow through system
```

### 2.4 Cost-Effective Migration Path

```
Phase 1 (Current): 100% Local Development
  ├── Docker Compose on local machine
  ├── Sample Avro files for testing
  ├── All services containerized
  └── Cost: $0/month

Phase 2 (Beta): Hybrid Deployment
  ├── Cloud storage (S3/GCS) for data lake
  ├── Local ETL worker for development
  ├── Cloud infrastructure for Health API
  └── Cost: ~$20-50/month

Phase 3 (Production): Full Cloud Deployment
  ├── Managed services for all components
  ├── Auto-scaling ETL workers
  ├── High availability
  └── Cost: ~$100-300/month (scales with usage)
```

---

## 3. Supported Health Data Types

Based on `services/health-api-service/app/supported_record_types.py`:

### 3.1 Record Types Overview

| Record Type | Clinical Focus | Sample Files | Clinical Value | Implementation Priority |
|-------------|---------------|--------------|----------------|------------------------|
| `BloodGlucoseRecord` | Diabetes management, glucose control, HbA1c estimation | 5 files | **Very High** - Critical for diabetes care | **1 - HIGH** |
| `HeartRateRecord` | Cardiovascular health, fitness, recovery patterns | 5 files | **High** - Cardiovascular fitness indicator | **2 - HIGH** |
| `SleepSessionRecord` | Sleep quality, recovery, sleep hygiene | 5 files | **High** - Holistic health foundation | **3 - MEDIUM** |
| `StepsRecord` | Physical activity, mobility, sedentary behavior | 5 files | **Medium** - Activity tracking | **5 - LOW** |
| `ActiveCaloriesBurnedRecord` | Energy expenditure, exercise intensity | 3 files | **Medium** - Exercise quantification | **6 - LOW** |
| `HeartRateVariabilityRmssdRecord` | Autonomic health, stress, training readiness | 3 files | **Medium** - Advanced fitness metric | **4 - MEDIUM** |

### 3.2 Clinical Processing Features by Type

**1. Blood Glucose Processor**
- Clinical ranges: normal, prediabetic, diabetic, hypoglycemic
- Time-in-range calculations (70-180 mg/dL target)
- Glycemic variability metrics (CV, MAGE)
- Estimated HbA1c calculation using ADAG formula
- Hypoglycemic/hyperglycemic event detection
- Dawn phenomenon analysis
- Meal relationship analysis (fasting, pre-meal, post-meal)

**2. Heart Rate Processor**
- Resting vs. active heart rate classification
- Heart rate zones analysis (5-zone model)
- Recovery patterns and cardiovascular fitness indicators
- Exercise session detection
- Basic arrhythmia detection (outlier detection)

**3. Sleep Session Processor**
- Sleep duration and efficiency calculation
- Sleep stage analysis (if available in data)
- Sleep schedule consistency assessment
- Sleep quality scoring
- Recommendations based on sleep hygiene guidelines

**4. Steps Processor**
- Daily activity levels and patterns
- Activity pattern analysis (hourly, weekly)
- Comparison to health guidelines (10,000 steps/day)
- Sedentary period detection

**5. Active Calories Processor**
- Energy expenditure patterns
- Activity intensity analysis
- Metabolic rate estimation
- Exercise session detection and characterization

**6. HRV Processor**
- RMSSD trend analysis
- Autonomic nervous system balance assessment
- Stress and recovery indicators
- Training readiness assessment

---

## 4. Message and Output Formats

### 4.1 Input Message Schema

**Message Format** (from RabbitMQ - `HealthDataMessage`):

```json
{
  "message_id": "uuid-v4",
  "correlation_id": "upload-correlation-id",
  "user_id": "user-identifier",
  "bucket": "health-data",
  "key": "raw/BloodGlucoseRecord/2025/11/15/user123_1731628800_abc123.avro",
  "record_type": "BloodGlucoseRecord",
  "upload_timestamp_utc": "2025-11-15T12:00:00Z",
  "content_hash": "sha256-hash",
  "file_size_bytes": 38664,
  "record_count": 287,
  "idempotency_key": "hash-based-key",
  "priority": "normal",
  "retry_count": 0
}
```

**Queue Configuration:**
- Queue: `health_data_processing`
- Exchange: `health_data_exchange` (topic)
- Routing Key: `health.processing.{record_type}.{priority}`
- Dead Letter Queue: `failed_queue`
- Prefetch Count: 1 (process one message at a time)

### 4.2 Output Format (Training Data)

**JSONL Training Data Schema:**

```json
{
  "instruction": "Analyze my blood glucose data from November 15, 2025 and provide detailed clinical insights including glucose control assessment and recommendations.",
  "output": "Your glucose monitoring data from November 15, 2025 shows 287 readings with an average glucose level of 142.3 mg/dL. You spent 65.2% of time in the target glucose range (70-180 mg/dL). This shows good glucose management. There were 3 low glucose episodes below 70 mg/dL. Your glucose variability is within acceptable limits (CV: 28.4%). Based on your average glucose, your estimated HbA1c is approximately 6.6%.",
  "metadata": {
    "source_s3_key": "raw/BloodGlucoseRecord/2025/11/15/user123_1731628800_abc123.avro",
    "source_bucket": "health-data",
    "record_type": "BloodGlucoseRecord",
    "upload_timestamp_utc": "2025-11-15T12:00:00Z",
    "user_id": "user123",
    "correlation_id": "upload-correlation-id",
    "processed_utc": "2025-11-15T12:05:23Z",
    "processing_id": "uuid-v4",
    "processor_version": "v3.0",
    "processing_duration_seconds": 2.34,
    "records_processed": 287,
    "data_quality_score": 0.98,
    "validation_warnings": [],
    "clinical_insights": {
      "glucose_statistics": {
        "mean": 142.3,
        "std": 40.5,
        "time_in_range": {
          "target_range": 65.2,
          "hypoglycemia": 1.4,
          "hyperglycemia": 33.4
        },
        "estimated_hba1c": 6.6,
        "hypoglycemic_events": {
          "hypo_events": 3,
          "severe_hypo_events": 0
        }
      },
      "temporal_patterns": {
        "collection_span_hours": 168.5,
        "peak_glucose_hour": 8,
        "dawn_phenomenon": {"elevation": 12.3}
      },
      "clinical_assessment": {
        "control_quality": "good",
        "variability": "low",
        "hypoglycemia_risk": "low"
      }
    },
    "training_category": "metabolic_diabetes",
    "complexity_level": "high_clinical",
    "clinical_relevance": "medium_clinical_relevance"
  }
}
```

### 4.3 File Organization in MinIO

```
health-data/                              # S3 Bucket
├── raw/                                  # Input files (read-only for ETL)
│   ├── BloodGlucoseRecord/
│   │   └── 2025/11/15/
│   │       └── user123_1731628800_abc123.avro
│   ├── HeartRateRecord/
│   │   └── 2025/11/15/
│   │       └── user456_1731628900_def456.avro
│   └── ...
│
├── training/                             # Output files (written by ETL)
│   ├── metabolic_diabetes/
│   │   └── 2025/11/
│   │       └── health_journal_2025_11.jsonl
│   ├── cardiovascular_fitness/
│   │   └── 2025/11/
│   │       └── health_journal_2025_11.jsonl
│   ├── sleep_recovery/
│   ├── physical_activity/
│   ├── energy_metabolism/
│   └── autonomic_health/
│
└── quarantine/                           # Failed validation files
    └── BloodGlucoseRecord/
        └── 2025/11/15/
            ├── user789_1731629000_xyz789.avro
            └── user789_1731629000_xyz789.metadata.json
```

**Storage Strategy:**
- **Monthly JSONL files**: One file per category per month (append mode)
- **Quarantine metadata**: Separate `.metadata.json` file explains quarantine reason
- **Hierarchical organization**: Category → Year → Month structure

---

## 5. Component Specifications

### 5.1 Service Structure

```
services/etl-narrative-engine/
├── src/
│   ├── __init__.py
│   ├── main.py                          # Entry point
│   ├── consumer/
│   │   ├── __init__.py
│   │   ├── etl_consumer.py             # Main message consumer
│   │   └── deduplication.py            # SQLite/Redis deduplication
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── base_processor.py           # Abstract clinical processor
│   │   ├── processor_factory.py        # Processor selection logic
│   │   ├── blood_glucose_processor.py  # Glucose-specific logic
│   │   ├── heart_rate_processor.py     # Heart rate processing
│   │   ├── sleep_processor.py          # Sleep analysis
│   │   ├── steps_processor.py          # Activity processing
│   │   ├── calories_processor.py       # Energy expenditure
│   │   └── hrv_processor.py            # HRV analysis
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── data_quality.py             # Quality validation
│   │   └── clinical_ranges.py          # Physiological ranges
│   ├── output/
│   │   ├── __init__.py
│   │   ├── narrative_generator.py      # Clinical narrative formatting
│   │   └── training_formatter.py       # JSONL training data
│   ├── storage/
│   │   ├── __init__.py
│   │   └── s3_client.py                # MinIO interactions
│   ├── monitoring/
│   │   ├── __init__.py
│   │   ├── metrics.py                  # Prometheus metrics
│   │   └── tracing.py                  # Jaeger tracing
│   └── config/
│       ├── __init__.py
│       └── settings.py                 # Pydantic settings
├── tests/
│   ├── __init__.py
│   ├── conftest.py                     # Test fixtures
│   ├── test_consumer.py                # Consumer tests
│   ├── test_processors/
│   │   ├── test_blood_glucose.py
│   │   ├── test_heart_rate.py
│   │   └── ...
│   ├── test_validation.py
│   ├── test_output.py
│   └── test_integration.py             # Full pipeline tests
├── scripts/
│   ├── load_sample_data.py             # Sample data loader
│   └── upload_to_health_api.py         # API upload helper
├── deployment/
│   ├── Dockerfile
│   ├── etl.compose.yml                 # Docker Compose config
│   └── .env.example
├── requirements.txt
├── pytest.ini
└── README.md
```

### 5.2 Base Clinical Processor Interface

```python
# src/processors/base_processor.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass
import pandas as pd
import numpy as np
import structlog

logger = structlog.get_logger()

@dataclass
class ProcessingResult:
    """Result of clinical processing"""
    success: bool
    narrative: str | None = None
    error_message: str | None = None
    processing_time_seconds: float = 0.0
    records_processed: int = 0
    quality_score: float = 1.0
    clinical_insights: Dict[str, Any] | None = None

class BaseClinicalProcessor(ABC):
    """Base class for clinical processors with domain expertise"""

    def __init__(self):
        self.clinical_ranges: Dict[str, Any] = {}
        self.reference_values: Dict[str, Any] = {}

    @abstractmethod
    async def process_with_clinical_insights(
        self,
        records: List[Dict[str, Any]],
        message_data: Dict[str, Any],
        validation_result: Any
    ) -> ProcessingResult:
        """Process records with clinical domain knowledge"""
        pass

    @abstractmethod
    async def initialize(self):
        """Initialize processor-specific configurations"""
        pass

    def _extract_temporal_patterns(
        self,
        df: pd.DataFrame,
        timestamp_col: str
    ) -> Dict[str, Any]:
        """Extract temporal patterns from data"""
        if df.empty or timestamp_col not in df.columns:
            return {}

        df[timestamp_col] = pd.to_datetime(df[timestamp_col])
        patterns = {}

        # Time of day patterns
        df['hour'] = df[timestamp_col].dt.hour
        patterns['hourly_distribution'] = df.groupby('hour').size().to_dict()

        # Day of week patterns
        df['day_of_week'] = df[timestamp_col].dt.day_name()
        patterns['daily_distribution'] = df.groupby('day_of_week').size().to_dict()

        # Data collection span
        time_span = df[timestamp_col].max() - df[timestamp_col].min()
        patterns['collection_span_hours'] = time_span.total_seconds() / 3600

        # Measurement frequency
        if len(df) > 1:
            avg_interval = time_span / (len(df) - 1)
            patterns['average_interval_minutes'] = avg_interval.total_seconds() / 60

        return patterns

    def _calculate_statistical_insights(
        self,
        values: np.ndarray
    ) -> Dict[str, Any]:
        """Calculate statistical insights for clinical interpretation"""
        if len(values) == 0:
            return {}

        insights = {
            'count': len(values),
            'mean': float(np.mean(values)),
            'median': float(np.median(values)),
            'std': float(np.std(values)),
            'min': float(np.min(values)),
            'max': float(np.max(values)),
            'range': float(np.max(values) - np.min(values)),
            'coefficient_of_variation': float(np.std(values) / np.mean(values))
                if np.mean(values) != 0 else 0
        }

        # Percentiles
        insights['percentiles'] = {
            '25th': float(np.percentile(values, 25)),
            '75th': float(np.percentile(values, 75)),
            '95th': float(np.percentile(values, 95))
        }

        # Outlier detection (IQR method)
        q1, q3 = np.percentile(values, [25, 75])
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        outliers = values[(values < lower_bound) | (values > upper_bound)]
        insights['outliers'] = {
            'count': len(outliers),
            'values': outliers.tolist() if len(outliers) <= 10 else outliers[:10].tolist()
        }

        return insights

    def _assess_data_quality_clinical(
        self,
        records: List[Dict],
        expected_patterns: Dict
    ) -> Dict[str, Any]:
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
        required_fields = expected_patterns.get('required_fields', [])
        if required_fields:
            complete_records = 0
            for record in records:
                field_count = sum(
                    1 for field in required_fields
                    if self._get_nested_value(record, field) is not None
                )
                complete_records += field_count / len(required_fields)
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
```

### 5.3 Blood Glucose Processor (Complete Implementation)

```python
# src/processors/blood_glucose_processor.py
from processors.base_processor import BaseClinicalProcessor, ProcessingResult
import pandas as pd
import numpy as np
from typing import List, Dict, Any
import structlog

logger = structlog.get_logger()

class BloodGlucoseProcessor(BaseClinicalProcessor):
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
            'hyperglycemic': (180, float('inf')),
            'target_range': (70, 180)
        }

        self.reference_values = {
            'time_in_range_excellent': 70,    # >70% TIR = excellent
            'time_in_range_good': 50,         # >50% TIR = good
            'cv_low': 36,                     # CV ≤36% = low variability
            'cv_moderate': 50                 # CV ≤50% = moderate
        }

    async def process_with_clinical_insights(
        self,
        records: List[Dict[str, Any]],
        message_data: Dict[str, Any],
        validation_result: Any
    ) -> ProcessingResult:
        """Process glucose data with comprehensive clinical analysis"""
        try:
            # 1. Convert to DataFrame
            df = self._records_to_dataframe(records)
            if df.empty:
                return ProcessingResult(
                    success=False,
                    error_message="No valid glucose data found"
                )

            # 2. Statistical analysis
            stats = self._analyze_glucose_statistics(df)

            # 3. Temporal patterns
            patterns = self._extract_temporal_patterns(df, 'timestamp')

            # 4. Clinical assessment
            assessment = self._assess_glucose_control(stats)

            # 5. Meal analysis
            meal_analysis = self._analyze_meal_relationships(df)

            # 6. Generate narrative
            narrative = self._generate_glucose_narrative(
                stats, patterns, assessment, meal_analysis, message_data
            )

            # 7. Compile insights
            clinical_insights = {
                'glucose_statistics': stats,
                'temporal_patterns': patterns,
                'clinical_assessment': assessment,
                'meal_analysis': meal_analysis,
                'recommendations': self._generate_recommendations(assessment)
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

    def _records_to_dataframe(self, records: List[Dict]) -> pd.DataFrame:
        """Convert Avro records to clinical DataFrame"""
        data = []
        for record in records:
            level = record.get('level', {})
            time_data = record.get('time', {})

            if level and 'inMilligramsPerDeciliter' in level:
                data.append({
                    'glucose_mg_dl': level['inMilligramsPerDeciliter'],
                    'timestamp': pd.to_datetime(time_data['epochMillis'], unit='ms'),
                    'meal_type': record.get('mealType', 'UNKNOWN'),
                    'specimen_source': record.get('specimenSource', 'UNKNOWN')
                })

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data).sort_values('timestamp').reset_index(drop=True)
        return df

    def _analyze_glucose_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Comprehensive glucose statistical analysis"""
        glucose_values = df['glucose_mg_dl'].values
        basic_stats = self._calculate_statistical_insights(glucose_values)

        return {
            **basic_stats,
            'time_in_range': self._calculate_time_in_range(glucose_values),
            'glycemic_variability': self._calculate_glycemic_variability(glucose_values),
            'estimated_hba1c': self._estimate_hba1c(glucose_values),
            'hypoglycemic_events': self._count_hypoglycemic_events(df),
            'hyperglycemic_events': self._count_hyperglycemic_events(df)
        }

    def _calculate_time_in_range(self, glucose_values: np.ndarray) -> Dict[str, float]:
        """Calculate time in various glucose ranges"""
        total = len(glucose_values)
        if total == 0:
            return {}

        return {
            'severe_hypoglycemia': np.sum(glucose_values < 54) / total * 100,
            'hypoglycemia': np.sum((glucose_values >= 54) & (glucose_values < 70)) / total * 100,
            'target_range': np.sum((glucose_values >= 70) & (glucose_values <= 180)) / total * 100,
            'hyperglycemia': np.sum((glucose_values > 180) & (glucose_values <= 250)) / total * 100,
            'severe_hyperglycemia': np.sum(glucose_values > 250) / total * 100
        }

    def _calculate_glycemic_variability(self, glucose_values: np.ndarray) -> Dict[str, float]:
        """Calculate measures of glycemic variability"""
        if len(glucose_values) < 2:
            return {}

        sd = np.std(glucose_values)
        cv = sd / np.mean(glucose_values) * 100 if np.mean(glucose_values) > 0 else 0

        # Simplified MAGE calculation
        diff = np.diff(glucose_values)
        peaks, troughs = [], []
        for i in range(1, len(diff)):
            if diff[i-1] > 0 and diff[i] <= 0:
                peaks.append(glucose_values[i])
            elif diff[i-1] < 0 and diff[i] >= 0:
                troughs.append(glucose_values[i])

        mage = 0
        if peaks and troughs:
            excursions = []
            for peak in peaks:
                for trough in troughs:
                    if abs(peak - trough) > sd:
                        excursions.append(abs(peak - trough))
            mage = np.mean(excursions) if excursions else 0

        return {
            'standard_deviation': sd,
            'coefficient_of_variation': cv,
            'mage': mage
        }

    def _estimate_hba1c(self, glucose_values: np.ndarray) -> float:
        """Estimate HbA1c from average glucose using ADAG formula"""
        if len(glucose_values) == 0:
            return 0.0
        # Formula: HbA1c (%) = (average glucose mg/dL + 46.7) / 28.7
        avg_glucose = np.mean(glucose_values)
        return round((avg_glucose + 46.7) / 28.7, 1)

    def _count_hypoglycemic_events(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Count and analyze hypoglycemic events"""
        hypo_readings = df[df['glucose_mg_dl'] < 70]
        severe_hypo_readings = df[df['glucose_mg_dl'] < 54]

        return {
            'total_hypo_readings': len(hypo_readings),
            'total_severe_hypo_readings': len(severe_hypo_readings),
            'hypo_events': len(hypo_readings) // 3,  # Simplified grouping
            'severe_hypo_events': len(severe_hypo_readings) // 3,
            'lowest_reading': float(df['glucose_mg_dl'].min()) if not df.empty else None
        }

    def _count_hyperglycemic_events(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Count and analyze hyperglycemic events"""
        hyper_readings = df[df['glucose_mg_dl'] > 180]
        severe_hyper_readings = df[df['glucose_mg_dl'] > 250]

        return {
            'total_hyper_readings': len(hyper_readings),
            'total_severe_hyper_readings': len(severe_hyper_readings),
            'hyper_events': len(hyper_readings) // 3,
            'severe_hyper_events': len(severe_hyper_readings) // 3,
            'highest_reading': float(df['glucose_mg_dl'].max()) if not df.empty else None
        }

    def _analyze_meal_relationships(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze glucose patterns related to meals"""
        meal_analysis = {}
        for meal_type in df['meal_type'].unique():
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

    def _assess_glucose_control(self, stats: Dict[str, Any]) -> Dict[str, Any]:
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
        if hypo_events.get('severe_hypo_events', 0) > 0:
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
        """Generate comprehensive glucose narrative"""
        narrative_parts = []

        # Header
        record_count = stats.get('count', 0)
        avg_glucose = stats.get('mean', 0)
        narrative_parts.append(
            f"Your glucose monitoring data shows {record_count} readings "
            f"with an average glucose level of {avg_glucose:.1f} mg/dL."
        )

        # Time in range
        tir = stats.get('time_in_range', {})
        target_time = tir.get('target_range', 0)
        narrative_parts.append(
            f"You spent {target_time:.1f}% of time in the target glucose range (70-180 mg/dL)."
        )

        # Control assessment
        control = assessment.get('control_quality', '')
        quality_descriptions = {
            'excellent': "This indicates excellent glucose control.",
            'good': "This shows good glucose management.",
            'fair': "This suggests room for improvement in glucose control.",
            'poor': "This indicates significant glucose management challenges."
        }
        narrative_parts.append(quality_descriptions.get(control, ''))

        # Hypoglycemia
        hypo_events = stats.get('hypoglycemic_events', {})
        if hypo_events.get('hypo_events', 0) > 0:
            narrative_parts.append(
                f"There were {hypo_events['hypo_events']} low glucose episodes below 70 mg/dL."
            )

        # Variability
        variability = stats.get('glycemic_variability', {})
        cv = variability.get('coefficient_of_variation', 0)
        narrative_parts.append(
            f"Your glucose variability is {assessment.get('variability', 'unknown')} (CV: {cv:.1f}%)."
        )

        # Estimated HbA1c
        estimated_hba1c = stats.get('estimated_hba1c', 0)
        if estimated_hba1c > 0:
            narrative_parts.append(
                f"Based on your average glucose, your estimated HbA1c is approximately {estimated_hba1c}%."
            )

        return " ".join(narrative_parts)

    def _generate_recommendations(self, assessment: Dict[str, Any]) -> List[str]:
        """Generate glucose-specific clinical recommendations"""
        recommendations = []

        control = assessment.get('control_quality', '')
        variability = assessment.get('variability', '')
        hypo_risk = assessment.get('hypoglycemia_risk', '')

        if control in ['fair', 'poor']:
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

### 5.4 Data Validation

**Data Quality Validator** (`validation/data_quality.py`):

```python
from typing import Dict, List, Any
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    quality_score: float
    metadata: Dict[str, Any]

class DataQualityValidator:
    """Validate data quality for health records"""

    def __init__(self):
        self.quality_threshold = 0.7  # Configurable

    async def validate(
        self,
        records: List[Dict],
        record_type: str,
        file_size_bytes: int
    ) -> ValidationResult:
        """Comprehensive data quality validation"""

        errors = []
        warnings = []
        metadata = {}

        # 1. Schema validation
        schema_valid = self._validate_schema(records, record_type)
        if not schema_valid:
            errors.append(f"Invalid schema for {record_type}")

        # 2. Completeness check
        completeness_score = self._check_completeness(records, record_type)
        metadata['completeness_score'] = completeness_score
        if completeness_score < 0.8:
            warnings.append(f"Low completeness: {completeness_score:.1%}")

        # 3. Physiological validity
        physiological_score = self._check_physiological_ranges(records, record_type)
        metadata['physiological_score'] = physiological_score
        if physiological_score < 0.9:
            warnings.append(f"Some values outside physiological ranges")

        # 4. Temporal consistency
        temporal_score = self._check_temporal_consistency(records)
        metadata['temporal_score'] = temporal_score

        # 5. Calculate overall quality score
        quality_score = (
            0.3 * (1.0 if schema_valid else 0.0) +
            0.3 * completeness_score +
            0.2 * physiological_score +
            0.2 * temporal_score
        )

        is_valid = quality_score >= self.quality_threshold and len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            quality_score=quality_score,
            metadata=metadata
        )

    def _validate_schema(self, records: List[Dict], record_type: str) -> bool:
        """Validate Avro schema compliance"""
        # Implementation depends on record type
        if not records:
            return False
        # Check required fields exist
        return True

    def _check_completeness(self, records: List[Dict], record_type: str) -> float:
        """Check data completeness"""
        if not records:
            return 0.0

        required_fields = {
            'BloodGlucoseRecord': ['level', 'time'],
            'HeartRateRecord': ['samples', 'time'],
            # ... other types
        }

        fields = required_fields.get(record_type, [])
        if not fields:
            return 1.0

        complete_count = sum(
            1 for record in records
            if all(field in record and record[field] for field in fields)
        )

        return complete_count / len(records)

    def _check_physiological_ranges(self, records: List[Dict], record_type: str) -> float:
        """Check values are within physiological ranges"""
        # Define ranges per record type
        ranges = {
            'BloodGlucoseRecord': {
                'field': 'level.inMilligramsPerDeciliter',
                'min': 20,
                'max': 600
            },
            'HeartRateRecord': {
                'field': 'samples.beatsPerMinute',
                'min': 30,
                'max': 220
            }
        }

        range_spec = ranges.get(record_type)
        if not range_spec:
            return 1.0

        # Check ranges
        valid_count = 0
        total_count = 0

        for record in records:
            value = self._get_nested_field(record, range_spec['field'])
            if value is not None:
                total_count += 1
                if range_spec['min'] <= value <= range_spec['max']:
                    valid_count += 1

        return valid_count / total_count if total_count > 0 else 0.0

    def _check_temporal_consistency(self, records: List[Dict]) -> float:
        """Check temporal ordering and consistency"""
        # Simplified: check if timestamps are monotonically increasing
        if len(records) < 2:
            return 1.0

        timestamps = [
            record.get('time', {}).get('epochMillis', 0)
            for record in records
        ]

        # Check for chronological order
        is_sorted = all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1))

        return 1.0 if is_sorted else 0.7

    def _get_nested_field(self, record: Dict, field_path: str) -> Any:
        """Get nested field using dot notation"""
        keys = field_path.split('.')
        value = record
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value
```

**Clinical Range Validator** (`validation/clinical_ranges.py`):

```python
from typing import Dict, Tuple

# Physiological ranges (extreme but possible values)
CLINICAL_RANGES: Dict[str, Dict[str, Tuple[float, float]]] = {
    'BloodGlucoseRecord': {
        'glucose_mg_dl': (20, 600),  # Extreme hypo to extreme hyper
    },
    'HeartRateRecord': {
        'heart_rate_bpm': (30, 220),  # Extreme bradycardia to extreme tachycardia
    },
    'SleepSessionRecord': {
        'duration_hours': (0.5, 16),  # Minimum nap to maximum sleep
    },
    'StepsRecord': {
        'count': (0, 100000),  # 0 to extreme activity
    },
    'ActiveCaloriesBurnedRecord': {
        'calories': (0, 10000),  # 0 to extreme exercise
    },
    'HeartRateVariabilityRmssdRecord': {
        'rmssd_ms': (1, 300),  # Very low HRV to very high HRV
    }
}

def get_clinical_range(record_type: str, field: str) -> Tuple[float, float] | None:
    """Get clinical range for a specific field"""
    return CLINICAL_RANGES.get(record_type, {}).get(field)
```

---

## 6. Configuration and Dependencies

### 6.1 Dependencies (`requirements.txt`)

```txt
# Core messaging and async
aio-pika==9.4.0              # Async RabbitMQ client
asyncio-mqtt==0.16.1         # Async support

# Data processing
pandas==2.1.4                # DataFrame operations
numpy==1.26.2                # Numerical computing
avro==1.11.3                 # Avro file parsing
fastavro==1.9.3              # Faster Avro parsing

# Clinical processing (Already in project)
scipy==1.11.4                # Statistical functions
scikit-learn==1.3.2          # ML utilities

# Storage
aioboto3==12.3.0             # Async S3 client for MinIO
aiosqlite==0.19.0            # Async SQLite for deduplication
redis==5.0.3                 # Redis client (for distributed dedup)

# Configuration
pydantic==2.5.0              # Data validation
pydantic-settings==2.1.0     # Environment config
python-dotenv==1.0.0         # .env file support

# Monitoring and Observability
structlog==24.1.0            # Structured logging
prometheus-client==0.19.0    # Metrics export
opentelemetry-api==1.22.0    # Tracing API
opentelemetry-sdk==1.22.0    # Tracing SDK
opentelemetry-exporter-otlp-proto-grpc==1.22.0  # Jaeger export
opentelemetry-instrumentation-aio-pika==0.43b0  # RabbitMQ tracing

# Error handling
tenacity==8.2.3              # Retry logic

# Testing (dev)
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
httpx==0.26.0                # For API testing
fakeredis==2.20.1            # Mock Redis
```

### 6.2 Environment Variables

```bash
# .env file for ETL Narrative Engine

# Service Identity
ETL_SERVICE_NAME=etl-narrative-engine
ETL_VERSION=v3.0

# Message Queue
ETL_RABBITMQ_URL=amqp://guest:guest@localhost:5672
ETL_QUEUE_NAME=health_data_processing
ETL_EXCHANGE_NAME=health_data_exchange
ETL_PREFETCH_COUNT=1
ETL_MAX_RETRIES=3
ETL_RETRY_DELAYS=[30,300,900]  # seconds: 30s, 5m, 15m

# Storage (MinIO Data Lake)
ETL_S3_ENDPOINT_URL=http://localhost:9000
ETL_S3_ACCESS_KEY=minioadmin
ETL_S3_SECRET_KEY=minioadmin
ETL_S3_BUCKET_NAME=health-data
ETL_S3_REGION=us-east-1

# Deduplication
ETL_DEDUPLICATION_STORE=sqlite  # or 'redis'
ETL_DEDUPLICATION_DB_PATH=/data/etl_processed_messages.db
ETL_DEDUPLICATION_REDIS_URL=redis://redis:6379/2
ETL_DEDUPLICATION_RETENTION_HOURS=168  # 7 days

# Data Quality
ETL_QUALITY_THRESHOLD=0.7
ETL_ENABLE_QUARANTINE=true
ETL_QUARANTINE_PREFIX=quarantine/

# Processing
ETL_MAX_FILE_SIZE_MB=100
ETL_MAX_RECORDS_PER_FILE=100000
ETL_PROCESSING_TIMEOUT_SECONDS=300

# Clinical Processing
ETL_ENABLE_CLINICAL_INSIGHTS=true
ETL_GENERATE_RECOMMENDATIONS=true

# Output
ETL_TRAINING_DATA_PREFIX=training/
ETL_TRAINING_FORMAT=jsonl
ETL_INCLUDE_METADATA=true

# Monitoring
ETL_ENABLE_METRICS=true
ETL_METRICS_PORT=8004
ETL_LOG_LEVEL=INFO
ETL_LOG_FORMAT=json  # or 'text'
ETL_ENABLE_JAEGER_TRACING=true
ETL_JAEGER_OTLP_ENDPOINT=http://localhost:4319  # Shared from webauthn-stack

# Development
ETL_DEVELOPMENT_MODE=false  # Set to true for additional debug logging
```

### 6.3 Pydantic Settings

```python
# src/config/settings.py
from pydantic_settings import BaseSettings
from typing import List
from enum import Enum

class DeduplicationStore(str, Enum):
    SQLITE = "sqlite"
    REDIS = "redis"

class LogFormat(str, Enum):
    JSON = "json"
    TEXT = "text"

class ETLSettings(BaseSettings):
    # Service
    service_name: str = "etl-narrative-engine"
    version: str = "v3.0"

    # Message Queue
    rabbitmq_url: str
    queue_name: str = "health_data_processing"
    exchange_name: str = "health_data_exchange"
    prefetch_count: int = 1
    max_retries: int = 3
    retry_delays: List[int] = [30, 300, 900]

    # Storage
    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket_name: str
    s3_region: str = "us-east-1"

    # Deduplication
    deduplication_store: DeduplicationStore = DeduplicationStore.SQLITE
    deduplication_db_path: str = "/data/etl_processed_messages.db"
    deduplication_redis_url: str = "redis://redis:6379/2"
    deduplication_retention_hours: int = 168

    # Data Quality
    quality_threshold: float = 0.7
    enable_quarantine: bool = True
    quarantine_prefix: str = "quarantine/"

    # Processing
    max_file_size_mb: int = 100
    max_records_per_file: int = 100000
    processing_timeout_seconds: int = 300

    # Clinical Processing
    enable_clinical_insights: bool = True
    generate_recommendations: bool = True

    # Output
    training_data_prefix: str = "training/"
    training_format: str = "jsonl"
    include_metadata: bool = True

    # Monitoring
    enable_metrics: bool = True
    metrics_port: int = 8004
    log_level: str = "INFO"
    log_format: LogFormat = LogFormat.JSON
    enable_jaeger_tracing: bool = True
    jaeger_otlp_endpoint: str = "http://localhost:4319"

    # Development
    development_mode: bool = False

    class Config:
        env_file = ".env"
        env_prefix = "ETL_"

settings = ETLSettings()
```

---

## 7. Deployment

### 7.1 Docker Configuration

**Dockerfile:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY scripts/ ./scripts/

# Create data directory for SQLite
RUN mkdir -p /data

# Run as non-root user
RUN useradd -m -u 1000 etlworker && \
    chown -R etlworker:etlworker /app /data
USER etlworker

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8004/health', timeout=5)" || exit 1

# Expose metrics port
EXPOSE 8004

# Run consumer
CMD ["python", "-m", "src.main"]
```

**docker-compose.yml** (addition to main compose file):

```yaml
# deployment/etl.compose.yml
services:
  etl-narrative-engine:
    build:
      context: ../../services/etl-narrative-engine
      dockerfile: deployment/Dockerfile
    container_name: etl-narrative-engine
    env_file:
      - ../../.env
    environment:
      ETL_RABBITMQ_URL: amqp://guest:guest@rabbitmq:5672
      ETL_S3_ENDPOINT_URL: http://minio:9000
      ETL_DEDUPLICATION_REDIS_URL: redis://redis:6379/2
      ETL_JAEGER_OTLP_ENDPOINT: http://host.docker.internal:4319
    depends_on:
      - rabbitmq
      - minio
      - redis
    volumes:
      - etl-data:/data  # Persistent SQLite storage
    ports:
      - "8004:8004"  # Metrics endpoint
    networks:
      - health-platform-net
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'

volumes:
  etl-data:
    driver: local

networks:
  health-platform-net:
    external: true
```

### 7.2 Local Development Setup

**Step-by-step guide:**

```bash
# 1. Start infrastructure
docker compose up -d minio rabbitmq redis postgres

# 2. Set up virtual environment
cd services/etl-narrative-engine
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp deployment/.env.example .env
# Edit .env with local configuration

# 5. Load sample data (Option B: Direct injection)
python scripts/load_sample_data.py --mode direct --all --user-id dev_user

# 6. Run ETL worker locally
export ETL_S3_ENDPOINT_URL=http://localhost:9000
export ETL_RABBITMQ_URL=amqp://guest:guest@localhost:5672
export ETL_DEDUPLICATION_STORE=sqlite
python -m src.main

# 7. Monitor progress
# - RabbitMQ Management: http://localhost:15672 (guest/guest)
# - MinIO Console: http://localhost:9001 (minioadmin/minioadmin)
# - Prometheus Metrics: http://localhost:8004/metrics
# - Jaeger UI: http://localhost:16687
```

### 7.3 Cloud Deployment Options

**Option 1: AWS ECS Fargate**
```yaml
Infrastructure:
  - ECR for Docker images
  - ECS Fargate for serverless containers
  - RDS PostgreSQL (health metadata)
  - ElastiCache Redis (deduplication)
  - S3 (data lake)
  - Amazon MQ (RabbitMQ managed)
  - CloudWatch (logging/metrics)
  - X-Ray (distributed tracing alternative)

Cost: ~$150-250/month for production workload
```

**Option 2: GCP Cloud Run**
```yaml
Infrastructure:
  - Artifact Registry for images
  - Cloud Run for ETL worker
  - Cloud SQL PostgreSQL
  - Memorystore Redis
  - Cloud Storage (data lake)
  - Cloud Pub/Sub (RabbitMQ alternative)
  - Cloud Logging/Monitoring
  - Cloud Trace (distributed tracing)

Cost: ~$120-200/month for production workload
```

**Option 3: Kubernetes** (Cloud-agnostic)
```yaml
Infrastructure:
  - Any Kubernetes cluster (EKS, GKE, AKS, self-hosted)
  - Horizontal Pod Autoscaling based on queue depth
  - Persistent volumes for SQLite dedup store
  - Ingress for metrics endpoint
  - Prometheus/Grafana for monitoring
  - Jaeger for distributed tracing

Cost: Variable based on cluster size and cloud provider
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

**Test Coverage Areas:**
- Clinical processors (each record type)
- Narrative generation quality
- Data validation logic
- Statistical calculations
- Error classification
- Training data formatting

**Example Test Structure:**

```python
# tests/test_processors/test_blood_glucose.py
import pytest
import numpy as np
from src.processors.blood_glucose_processor import BloodGlucoseProcessor

@pytest.mark.asyncio
async def test_glucose_time_in_range_calculation():
    """Test time-in-range calculation accuracy"""
    processor = BloodGlucoseProcessor()
    await processor.initialize()

    # Test data with known distribution
    glucose_values = np.array([
        50,   # severe hypo
        65,   # hypo
        80, 120, 150,  # target range (3)
        200,  # hyper
        260   # severe hyper
    ])

    tir = processor._calculate_time_in_range(glucose_values)

    assert tir['severe_hypoglycemia'] == pytest.approx(14.3, rel=0.1)  # 1/7
    assert tir['target_range'] == pytest.approx(42.9, rel=0.1)          # 3/7
    assert tir['hyperglycemia'] == pytest.approx(14.3, rel=0.1)         # 1/7
    assert tir['severe_hyperglycemia'] == pytest.approx(14.3, rel=0.1)  # 1/7

@pytest.mark.asyncio
async def test_hba1c_estimation():
    """Test HbA1c estimation formula"""
    processor = BloodGlucoseProcessor()
    await processor.initialize()

    # Average glucose of 154 mg/dL should estimate ~7.0% HbA1c
    glucose_values = np.array([154] * 100)
    estimated_hba1c = processor._estimate_hba1c(glucose_values)

    assert estimated_hba1c == pytest.approx(7.0, abs=0.1)

@pytest.mark.asyncio
async def test_glucose_processor_full_pipeline():
    """Test complete glucose processing pipeline"""
    processor = BloodGlucoseProcessor()
    await processor.initialize()

    # Load sample records
    records = load_sample_glucose_records()
    message_data = {
        'record_type': 'BloodGlucoseRecord',
        'user_id': 'test_user',
        'upload_timestamp_utc': '2025-11-15T12:00:00Z'
    }

    result = await processor.process_with_clinical_insights(
        records, message_data, mock_validation_result
    )

    assert result.success
    assert result.narrative is not None
    assert "time in range" in result.narrative.lower()
    assert result.clinical_insights is not None
    assert 'glucose_statistics' in result.clinical_insights
    assert 'clinical_assessment' in result.clinical_insights
```

### 8.2 Integration Tests

**Test Scenarios:**

**1. End-to-End Processing:**
```python
# tests/test_integration.py
@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_pipeline_blood_glucose(
    rabbitmq_connection,
    minio_client,
    deduplication_store
):
    """Test full pipeline: RabbitMQ → Download → Process → Output"""

    # 1. Upload sample file to MinIO
    sample_file = "docs/sample-avro-files/BloodGlucoseRecord_1758407139312.avro"
    with open(sample_file, 'rb') as f:
        await minio_client.put_object(
            bucket='health-data',
            key='raw/BloodGlucoseRecord/2025/11/15/test_user_123.avro',
            data=f.read()
        )

    # 2. Publish message to RabbitMQ
    message = create_test_message(
        bucket='health-data',
        key='raw/BloodGlucoseRecord/2025/11/15/test_user_123.avro',
        user_id='test_user',
        record_type='BloodGlucoseRecord'
    )
    await publish_message(rabbitmq_connection, message)

    # 3. Wait for processing (consumer running in background)
    await asyncio.sleep(5)

    # 4. Verify deduplication store updated
    is_processed = await deduplication_store.is_already_processed(
        message['idempotency_key']
    )
    assert is_processed

    # 5. Verify training data created in MinIO
    training_files = await minio_client.list_objects(
        bucket='health-data',
        prefix='training/metabolic_diabetes/2025/11/'
    )
    assert len(training_files) > 0

    # 6. Verify training data format
    training_content = await minio_client.get_object(
        bucket='health-data',
        key=training_files[0]
    )
    training_entry = json.loads(training_content.split('\n')[0])
    assert 'instruction' in training_entry
    assert 'output' in training_entry
    assert 'metadata' in training_entry
    assert training_entry['metadata']['record_type'] == 'BloodGlucoseRecord'
```

**2. Idempotency Test:**
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_message_idempotency(rabbitmq_connection, minio_client):
    """Verify duplicate messages are not reprocessed"""

    # Process same message twice
    message = create_test_message(idempotency_key='duplicate_test_123')

    await publish_message(rabbitmq_connection, message)
    await asyncio.sleep(3)

    await publish_message(rabbitmq_connection, message)
    await asyncio.sleep(3)

    # Verify only one training output created
    training_files = await minio_client.list_objects(
        bucket='health-data',
        prefix='training/'
    )

    # Count entries with same processing_id
    entries = []
    for file_key in training_files:
        content = await minio_client.get_object(bucket='health-data', key=file_key)
        entries.extend(json.loads(line) for line in content.split('\n') if line)

    matching_entries = [
        e for e in entries
        if e['metadata'].get('idempotency_key') == 'duplicate_test_123'
    ]

    assert len(matching_entries) == 1, "Duplicate processing detected!"
```

**3. Quarantine Flow Test:**
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_low_quality_data_quarantine(rabbitmq_connection, minio_client):
    """Verify low-quality data is quarantined"""

    # Create low-quality Avro file (missing required fields)
    low_quality_file = create_invalid_avro_file()

    await minio_client.put_object(
        bucket='health-data',
        key='raw/BloodGlucoseRecord/2025/11/15/low_quality.avro',
        data=low_quality_file
    )

    message = create_test_message(
        key='raw/BloodGlucoseRecord/2025/11/15/low_quality.avro'
    )
    await publish_message(rabbitmq_connection, message)
    await asyncio.sleep(3)

    # Verify file moved to quarantine
    quarantine_files = await minio_client.list_objects(
        bucket='health-data',
        prefix='quarantine/BloodGlucoseRecord/'
    )
    assert len(quarantine_files) > 0

    # Verify metadata explains quarantine reason
    metadata_key = quarantine_files[0] + '.metadata.json'
    metadata = json.loads(
        await minio_client.get_object(bucket='health-data', key=metadata_key)
    )
    assert 'quarantine_reason' in metadata
    assert 'quality_score' in metadata
```

### 8.3 Test Fixtures

```python
# tests/conftest.py
import pytest
import asyncio
from testcontainers.rabbitmq import RabbitMqContainer
from testcontainers.minio import MinioContainer
from testcontainers.redis import RedisContainer

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def rabbitmq_container():
    """Start RabbitMQ container for tests"""
    with RabbitMqContainer("rabbitmq:3.12-management") as rabbitmq:
        yield rabbitmq

@pytest.fixture(scope="session")
async def minio_container():
    """Start MinIO container for tests"""
    with MinioContainer("minio/minio:latest") as minio:
        # Create bucket
        client = minio.get_client()
        client.make_bucket("health-data")
        yield minio

@pytest.fixture(scope="session")
async def redis_container():
    """Start Redis container for tests"""
    with RedisContainer("redis:7-alpine") as redis:
        yield redis

@pytest.fixture
async def deduplication_store():
    """Create in-memory SQLite deduplication store"""
    from src.consumer.deduplication import DeduplicationStore
    store = DeduplicationStore(db_path=":memory:")
    await store.initialize()
    yield store
    await store.close()
```

### 8.4 Quality Assurance Metrics

**Target Test Coverage:**
- ✅ >80% code coverage overall
- ✅ 100% coverage for critical paths (deduplication, clinical processors)
- ✅ All 6 record types tested with sample files
- ✅ Edge cases covered (empty files, malformed data, network errors)

**Narrative Quality Checks:**
- Grammar and spelling validation
- Clinical accuracy review (spot check by domain expert)
- Tone and language appropriateness
- Completeness of information

**Performance Benchmarks:**
- Process 500 glucose records in <5 seconds
- Process all 26 sample files in <60 seconds
- Deduplication check in <10ms
- Training data write in <100ms

---

## 9. Monitoring and Observability

### 9.1 Prometheus Metrics

```python
# src/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Summary, start_http_server

# Processing metrics
messages_processed_total = Counter(
    'etl_messages_processed_total',
    'Total messages processed',
    ['record_type', 'status']  # status: success, failed, quarantined
)

processing_duration_seconds = Histogram(
    'etl_processing_duration_seconds',
    'Time spent processing messages',
    ['record_type'],
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120, 300]
)

records_processed_total = Counter(
    'etl_records_processed_total',
    'Total health records processed',
    ['record_type']
)

# Quality metrics
data_quality_score = Summary(
    'etl_data_quality_score',
    'Data quality scores',
    ['record_type']
)

quarantined_files_total = Counter(
    'etl_quarantined_files_total',
    'Total files quarantined',
    ['record_type', 'reason']
)

# Deduplication metrics
duplicate_messages_total = Counter(
    'etl_duplicate_messages_total',
    'Total duplicate messages skipped',
    ['record_type']
)

deduplication_store_size = Gauge(
    'etl_deduplication_store_size',
    'Number of entries in deduplication store'
)

# Error metrics
processing_errors_total = Counter(
    'etl_processing_errors_total',
    'Total processing errors',
    ['error_type', 'record_type']
)

retry_attempts_total = Counter(
    'etl_retry_attempts_total',
    'Total retry attempts',
    ['record_type', 'retry_number']
)

# Training data metrics
training_data_generated_total = Counter(
    'etl_training_data_generated_total',
    'Total training data entries generated',
    ['category']
)

training_data_size_bytes = Summary(
    'etl_training_data_size_bytes',
    'Size of generated training data',
    ['category']
)

# Consumer health
rabbitmq_connected = Gauge(
    'etl_rabbitmq_connected',
    'RabbitMQ connection status (1=connected, 0=disconnected)'
)

s3_accessible = Gauge(
    'etl_s3_accessible',
    'S3 storage accessibility (1=accessible, 0=inaccessible)'
)

def start_metrics_server(port: int = 8004):
    """Start Prometheus metrics HTTP server"""
    start_http_server(port)
```

**Metrics Endpoint**: `http://localhost:8004/metrics`

### 9.2 Health Check Endpoint

```python
# src/monitoring/health.py
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
import time

app = FastAPI()
start_time = time.time()

@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration"""
    try:
        # Check RabbitMQ connection
        rabbitmq_ok = await check_rabbitmq_connection()

        # Check S3 accessibility
        s3_ok = await check_s3_access()

        # Check deduplication store
        dedup_ok = await check_deduplication_store()

        all_healthy = rabbitmq_ok and s3_ok and dedup_ok

        return JSONResponse(
            status_code=status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "healthy" if all_healthy else "unhealthy",
                "rabbitmq_connected": rabbitmq_ok,
                "s3_accessible": s3_ok,
                "deduplication_store_healthy": dedup_ok,
                "uptime_seconds": int(time.time() - start_time)
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "error": str(e)}
        )
```

### 9.3 Distributed Tracing (Jaeger)

**Integration with Jaeger** (from webauthn-stack):

```python
# src/monitoring/tracing.py
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.aio_pika import AioPikaInstrumentor
from src.config.settings import settings
import structlog

logger = structlog.get_logger()

def setup_tracing():
    """Configure distributed tracing with Jaeger"""

    if not settings.enable_jaeger_tracing:
        logger.info("Jaeger tracing disabled")
        return

    # Set up tracer provider
    resource = Resource.create({
        "service.name": settings.service_name,
        "service.version": settings.version,
        "deployment.environment": "development" if settings.development_mode else "production"
    })

    provider = TracerProvider(resource=resource)

    # Configure OTLP exporter to Jaeger (from webauthn-stack)
    otlp_exporter = OTLPSpanExporter(
        endpoint=settings.jaeger_otlp_endpoint,
        insecure=True
    )

    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    trace.set_tracer_provider(provider)

    # Auto-instrument libraries
    AioPikaInstrumentor().instrument()

    logger.info("Jaeger tracing configured", endpoint=settings.jaeger_otlp_endpoint)

tracer = trace.get_tracer(__name__)

# Usage in consumer:
# with tracer.start_as_current_span("process_health_message") as span:
#     span.set_attribute("record_type", message_data['record_type'])
#     span.set_attribute("user_id", message_data['user_id'])
#     result = await process_health_data(message_data)
#     span.set_attribute("quality_score", result.quality_score)
```

**Jaeger UI**: `http://localhost:16687` (from webauthn-stack)

### 9.4 Structured Logging

```python
# src/monitoring/logging_config.py
import structlog
import logging
from src.config.settings import settings

def configure_logging():
    """Configure structured logging with structlog"""

    # Determine processors based on log format
    if settings.log_format == "json":
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ]
    else:  # text format
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer()
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.log_level.upper())
    )

# Usage:
# logger = structlog.get_logger()
# logger.info(
#     "Processing message",
#     correlation_id=correlation_id,
#     record_type=record_type,
#     user_id=user_id
# )
```

**Log Levels:**
- **DEBUG**: Detailed processing steps (development only)
- **INFO**: Message processed, training data generated
- **WARNING**: Low quality data, retry scheduled
- **ERROR**: Processing failed, quarantine, DLQ
- **CRITICAL**: Service initialization failed, cannot connect to dependencies

### 9.5 Alerting Thresholds

| Metric | Threshold | Severity | Action |
|--------|-----------|----------|--------|
| **Processing success rate** | < 90% | WARNING | Investigate errors, check logs |
| **Processing success rate** | < 75% | CRITICAL | Immediate attention, potential outage |
| **Quarantine rate** | > 10% | WARNING | Check data quality from source |
| **Queue depth** | > 1000 messages | WARNING | Scale workers or increase processing |
| **Message processing time (p95)** | > 60s | WARNING | Optimize processing or scale horizontally |
| **Deduplication store size** | > 1M records | INFO | Consider cleanup or increase retention |
| **RabbitMQ disconnections** | > 3 in 5min | CRITICAL | Check network, RabbitMQ health |
| **S3 access failures** | > 5% of requests | CRITICAL | Check MinIO/S3 connectivity |

---

## 10. Security Considerations

### 10.1 Data Privacy

- **PHI Handling**: All health data is Protected Health Information (PHI) under HIPAA
- **Encryption in Transit**: TLS for S3 API calls (when using production MinIO/S3 with TLS)
- **Encryption at Rest**: MinIO bucket encryption enabled in production
- **Access Control**: Service uses dedicated S3 credentials with least-privilege access
- **Audit Logging**: All data access logged with correlation IDs for traceability

### 10.2 Authentication

**MinIO/S3:**
- Access key and secret key (stored in environment variables)
- Least-privilege IAM policies in production
- Separate credentials per environment (dev, staging, production)

**RabbitMQ:**
- Username and password authentication
- Default: `guest/guest` for local development only
- Secure credentials with TLS for production deployments
- Virtual hosts for environment isolation

**Redis:**
- Optional password authentication
- Network isolation (not exposed publicly)
- Separate database numbers per service

### 10.3 Secrets Management

**Development:**
- `.env` file (not committed to git, in `.gitignore`)
- Environment variables passed to Docker containers
- Local credentials with no real PHI

**Production:**
- **Kubernetes**: Kubernetes Secrets with encryption at rest
- **AWS**: AWS Secrets Manager with automatic rotation
- **GCP**: GCP Secret Manager with IAM policies
- **Azure**: Azure Key Vault with managed identities
- **Alternative**: HashiCorp Vault for multi-cloud deployments

**Best Practices:**
- Never hardcode secrets in code
- Rotate credentials regularly (90 days)
- Use service accounts with minimal permissions
- Audit secret access

### 10.4 Network Security

**Local Development:**
- All services on Docker network (isolated from host)
- Expose only necessary ports (metrics, management UIs)

**Production:**
- Private VPC/VNET for all services
- Security groups/firewall rules limiting traffic
- No direct internet exposure for backend services
- API Gateway/Load Balancer for external access only

---

## 11. Performance and Scaling

### 11.1 Throughput Targets

**Expected Load:**
- **Average**: 10 messages/minute (~600/hour, ~14,400/day)
- **Peak**: 50 messages/minute (~3,000/hour during busy periods)
- **Message processing time**: < 5 seconds (p95), < 10 seconds (p99)

**Scaling Strategy:**
- **Single worker**: 10-20 messages/minute
- **Horizontal scaling**: Run multiple workers with Redis deduplication
- **Prefetch limit**: 1 (for fair work distribution across workers)
- **Auto-scaling trigger**: Queue depth > 500 messages

### 11.2 Resource Requirements

**Single Worker Instance:**
- **CPU**: 1-2 cores (1 core sufficient for baseline, 2 cores for peak)
- **Memory**: 2-4 GB (pandas DataFrames can be memory-intensive)
- **Disk**: 10 GB (for logs and SQLite deduplication DB)
- **Network**: Minimal bandwidth (~50KB-100KB per message for S3 downloads)

**Optimizations:**
- Stream large files from S3 instead of loading into memory
- Process records in batches for statistical calculations
- Reuse boto3 clients (connection pooling)
- Cache clinical ranges and reference values
- Use `fastavro` for faster Avro parsing

### 11.3 Horizontal Scaling

**Requirements for multi-instance deployment:**
1. **Switch to Redis deduplication** (from SQLite)
   ```bash
   ETL_DEDUPLICATION_STORE=redis
   ETL_DEDUPLICATION_REDIS_URL=redis://redis:6379/2
   ```

2. **Deploy multiple worker containers**
   ```bash
   docker compose up -d --scale etl-narrative-engine=3
   ```

3. **Monitor queue depth** and scale based on load
   - Kubernetes: Horizontal Pod Autoscaler (HPA)
   - AWS ECS: Target tracking scaling policy
   - Manual: Scale based on CloudWatch/Prometheus metrics

**Scaling Formula:**
```
Target workers = ceil(queue_depth / (throughput_per_worker * target_latency_minutes))

Example:
- Queue depth: 1000 messages
- Throughput per worker: 15 messages/minute
- Target latency: 5 minutes
- Target workers = ceil(1000 / (15 * 5)) = ceil(13.3) = 14 workers
```

---

## 12. Implementation Roadmap

### Week 1: Foundation & Infrastructure
- [x] Set up project structure
- [ ] Implement Pydantic settings and configuration
- [ ] Create SQLite deduplication store
- [ ] Implement basic RabbitMQ consumer skeleton
- [ ] Set up S3 file download logic
- [ ] Create Avro record extraction utility
- [ ] Write sample data loader script (Appendix A)
- [ ] Set up pytest configuration and fixtures
- [ ] Configure structured logging

### Week 2: Core Processing Logic
- [ ] Implement complete message consumer with idempotency
- [ ] Create base clinical processor interface
- [ ] Implement data quality validator
- [ ] Implement clinical range validator
- [ ] Create processor factory
- [ ] Implement error classification logic
- [ ] Set up retry mechanism with RabbitMQ
- [ ] Write unit tests for core consumer

### Week 3: Clinical Processors (Priority Order)
- [ ] **Implement BloodGlucoseProcessor** (HIGH priority)
  - [ ] Time-in-range calculation
  - [ ] Glycemic variability metrics
  - [ ] HbA1c estimation
  - [ ] Event detection
  - [ ] Unit tests
- [ ] **Implement HeartRateProcessor** (HIGH priority)
  - [ ] Heart rate zones
  - [ ] Recovery patterns
  - [ ] Unit tests
- [ ] **Implement SleepProcessor** (MEDIUM priority)
  - [ ] Sleep duration/efficiency
  - [ ] Sleep quality scoring
  - [ ] Unit tests

### Week 4: Training Data Output & Remaining Processors
- [ ] Implement narrative generator
- [ ] Implement training data formatter (JSONL)
- [ ] Implement contextual instruction generation
- [ ] Implement S3 append logic for training files
- [ ] **Implement StepsProcessor** (LOW priority)
- [ ] **Implement CaloriesProcessor** (LOW priority)
- [ ] **Implement HRVProcessor** (MEDIUM priority)
- [ ] Test training data quality and format
- [ ] Write unit tests for all processors

### Week 5: Testing & Quality Assurance
- [ ] Write comprehensive integration tests
  - [ ] End-to-end pipeline test
  - [ ] Idempotency test
  - [ ] Quarantine flow test
  - [ ] Error handling test
- [ ] Test all 26 sample files
- [ ] Verify training data output for each record type
- [ ] Performance testing (process 500 records < 5s)
- [ ] Load testing with concurrent messages
- [ ] Code coverage analysis (target: >80%)
- [ ] Narrative quality review (spot check)

### Week 6: Deployment & Observability
- [ ] Create Dockerfile with non-root user
- [ ] Create docker-compose configuration
- [ ] Implement Prometheus metrics
- [ ] Set up Jaeger tracing integration
- [ ] Implement health check endpoint
- [ ] Configure alerting thresholds
- [ ] Write deployment documentation
- [ ] Create operational runbook
- [ ] Security review
- [ ] Documentation review and finalization

---

## 13. Success Criteria & Validation

### 13.1 Functional Requirements
- ✅ Process all 6 supported health data types
- ✅ Generate clinically accurate narratives for each type
- ✅ Write training data in JSONL format to MinIO (`training/` prefix)
- ✅ Implement idempotent processing (no duplicate outputs)
- ✅ Handle errors gracefully with retry logic
- ✅ Quarantine low-quality data with metadata
- ✅ Support both SQLite and Redis deduplication

### 13.2 Non-Functional Requirements
- ✅ Process messages within 5 seconds (p95), 10 seconds (p99)
- ✅ Achieve >95% processing success rate
- ✅ Maintain data quality score >0.85 average
- ✅ Zero data loss (all messages accounted for via deduplication + DLQ)
- ✅ Comprehensive logging with correlation IDs
- ✅ Prometheus metrics exported on port 8004
- ✅ Distributed tracing to Jaeger
- ✅ Easy local development setup (< 10 minutes from clone to running)

### 13.3 Quality Gates
- ✅ >80% unit test coverage overall
- ✅ 100% coverage for critical paths (deduplication, clinical processors)
- ✅ All integration tests passing
- ✅ All 26 sample files process successfully
- ✅ Narrative quality review by domain expert (spot check 10% of outputs)
- ✅ Security review passed (no hardcoded secrets, PHI handling correct)
- ✅ Documentation complete (README, API docs, deployment guide)
- ✅ Performance benchmarks met (process 500 records < 5s)

### 13.4 Development Requirements
- ✅ Complete local development without cloud dependencies
- ✅ Sample data loader works with all 26 files
- ✅ Docker Compose brings up entire stack
- ✅ Fast iteration cycle (< 30 seconds to test changes)

### 13.5 Integration Requirements
- ✅ Compatible with existing RabbitMQ message format
- ✅ Reads from `raw/` prefix in MinIO correctly
- ✅ Writes to `training/` and `quarantine/` prefixes
- ✅ Uses shared Jaeger from webauthn-stack
- ✅ Independent SQLite deduplication (no shared Redis required for single instance)
- ✅ Metrics compatible with Prometheus scraping

---

## 14. Open Questions & Decisions

### 14.1 Resolved ✅
- **Data Source**: Use existing sample AVRO files in `docs/sample-avro-files/`
- **Deduplication**: SQLite for single instance, Redis for multi-instance
- **Output Format**: JSONL with comprehensive metadata
- **Development Strategy**: Local-first, cloud deployment later
- **Observability**: Prometheus + Jaeger + structured logging
- **Security**: Non-root Docker user, secrets in environment variables

### 14.2 To Be Decided 🔜
- **Clinical Validation**: Should we have a healthcare professional review generated narratives before production deployment?
- **User Feedback Loop**: How will users provide feedback on narrative quality/accuracy? API endpoint? Survey?
- **Production Deployment Target**: AWS ECS, GCP Cloud Run, or Kubernetes? (Decision can wait until production readiness)
- **Monitoring Stack**: Self-hosted Prometheus + Grafana, or managed service (CloudWatch, Stackdriver, Datadog)?
- **Alerting Destination**: PagerDuty, Slack, email, or other?
- **Backup Strategy**: How often should training data be backed up? Retention policy?
- **Compliance**: Do we need HIPAA compliance certification? (Affects deployment architecture)

---

## 15. Risk Analysis & Mitigation

| Risk | Impact | Probability | Mitigation Strategy |
|------|--------|-------------|---------------------|
| **Avro schema changes from Android app** | High | Medium | - Version schema in files<br>- Support backward compatibility<br>- Schema validation in upload API<br>- Alert on schema changes |
| **Memory exhaustion from large files** | High | Low | - Stream processing (no full file in memory)<br>- File size limits (100MB)<br>- Record count limits (100K)<br>- Memory monitoring and alerts |
| **Message loss (RabbitMQ failure)** | High | Low | - Persistent RabbitMQ queues<br>- Manual ACK only after processing complete<br>- Dead letter queue for failures<br>- Monitoring of queue depth |
| **Deduplication DB corruption** | Medium | Low | - Regular SQLite backups (hourly)<br>- WAL mode for crash safety<br>- Redis fallback option<br>- Deduplication recovery procedure |
| **Processor crashes during processing** | Medium | Medium | - Comprehensive error handling<br>- Try-catch in all processors<br>- Message requeue on crash<br>- Health checks and auto-restart |
| **Training data quality issues** | Medium | Medium | - Validation tests for narratives<br>- Spot checks by domain expert<br>- Quality metrics tracking<br>- A/B testing of processor changes |
| **Dependency version conflicts** | Low | Medium | - Test with existing project dependencies first<br>- Pin versions in requirements.txt<br>- Automated dependency updates with tests |
| **Cloud migration complexity** | Medium | High | - Docker-first approach ensures portability<br>- Test locally before cloud deployment<br>- Gradual migration (hybrid phase)<br>- Infrastructure-as-code (Terraform/Pulumi) |
| **Performance degradation under load** | Medium | Medium | - Performance benchmarks in CI<br>- Load testing before production<br>- Horizontal scaling capability<br>- Auto-scaling policies |
| **Security vulnerability in dependencies** | High | Low | - Regular dependency scanning (Snyk, Dependabot)<br>- Automated security updates<br>- Security review before production |

---

## Appendix A: Sample Data Loader Script

**Complete Implementation** (`scripts/load_sample_data.py`):

```python
#!/usr/bin/env python3
"""
scripts/load_sample_data.py

Load sample Avro files into the system for ETL development and testing.

This script provides two modes:
1. Via Health API: Upload files through the Health API service (end-to-end test)
2. Direct Injection: Upload to MinIO + publish to RabbitMQ directly (faster iteration)

Usage:
    # Load all sample files via Health API
    python scripts/load_sample_data.py --mode api --all --auth-token YOUR_TOKEN

    # Load specific record type via direct injection
    python scripts/load_sample_data.py --mode direct --record-type BloodGlucoseRecord

    # Load with custom user ID
    python scripts/load_sample_data.py --mode direct --all --user-id test_user_123
"""

import asyncio
import argparse
import json
import hashlib
import uuid
from pathlib import Path
from datetime import datetime
from typing import List
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import aioboto3
import aio_pika
from fastavro import reader

# Configuration
SAMPLE_FILES_DIR = Path("docs/sample-avro-files")
HEALTH_API_URL = "http://localhost:8001"
MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
MINIO_BUCKET = "health-data"
RABBITMQ_URL = "amqp://guest:guest@localhost:5672"
EXCHANGE_NAME = "health_data_exchange"


async def load_via_api(files: List[Path], auth_token: str):
    """Load sample files via Health API service"""
    print(f"\n{'='*60}")
    print(f"Loading {len(files)} file(s) via Health API")
    print(f"{'='*60}\n")

    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, file_path in enumerate(files, 1):
            print(f"[{i}/{len(files)}] Uploading {file_path.name}...")

            with open(file_path, 'rb') as f:
                files_dict = {'file': (file_path.name, f, 'application/octet-stream')}
                headers = {'Authorization': f'Bearer {auth_token}'}

                try:
                    response = await client.post(
                        f"{HEALTH_API_URL}/v1/upload",
                        files=files_dict,
                        headers=headers
                    )

                    if response.status_code == 200:
                        result = response.json()
                        print(f"  ✅ Success: correlation_id={result.get('correlation_id')}")
                    else:
                        print(f"  ❌ Failed: {response.status_code} - {response.text}")

                except Exception as e:
                    print(f"  ❌ Error: {e}")

    print(f"\n{'='*60}")
    print(f"API upload complete")
    print(f"{'='*60}\n")


async def load_via_direct_injection(files: List[Path], user_id: str):
    """Load sample files directly to MinIO and RabbitMQ"""
    print(f"\n{'='*60}")
    print(f"Loading {len(files)} file(s) via Direct Injection")
    print(f"User ID: {user_id}")
    print(f"{'='*60}\n")

    # Initialize S3 client
    session = aioboto3.Session()
    async with session.client(
        's3',
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY
    ) as s3_client:

        # Initialize RabbitMQ connection
        try:
            connection = await aio_pika.connect_robust(RABBITMQ_URL)
            channel = await connection.channel()
            exchange = await channel.get_exchange(EXCHANGE_NAME)
        except Exception as e:
            print(f"❌ Failed to connect to RabbitMQ: {e}")
            print("   Make sure RabbitMQ is running: docker compose up -d rabbitmq")
            return

        for i, file_path in enumerate(files, 1):
            print(f"[{i}/{len(files)}] Processing {file_path.name}...")

            try:
                # Extract record type from filename
                record_type = file_path.stem.rsplit('_', 1)[0]  # Remove timestamp

                # Read file content
                with open(file_path, 'rb') as f:
                    file_content = f.read()

                # Calculate hash
                content_hash = hashlib.sha256(file_content).hexdigest()[:16]

                # Count records
                record_count = 0
                with open(file_path, 'rb') as f:
                    avro_reader = reader(f)
                    record_count = sum(1 for _ in avro_reader)

                # Generate S3 key
                now = datetime.utcnow()
                timestamp = int(now.timestamp())
                s3_key = (
                    f"raw/{record_type}/{now.year}/{now.month:02d}/{now.day:02d}/"
                    f"{user_id}_{timestamp}_{content_hash}.avro"
                )

                # Upload to MinIO
                await s3_client.put_object(
                    Bucket=MINIO_BUCKET,
                    Key=s3_key,
                    Body=file_content,
                    ContentType='application/avro'
                )
                print(f"  ✅ Uploaded to MinIO: {s3_key}")

                # Publish message to RabbitMQ
                message_data = {
                    'bucket': MINIO_BUCKET,
                    'key': s3_key,
                    'user_id': user_id,
                    'record_type': record_type,
                    'upload_timestamp_utc': now.isoformat() + 'Z',
                    'message_id': str(uuid.uuid4()),
                    'correlation_id': str(uuid.uuid4()),
                    'idempotency_key': f"{user_id}:{content_hash}:{timestamp}",
                    'content_hash': content_hash,
                    'priority': 'normal',
                    'retry_count': 0,
                    'file_size_bytes': len(file_content),
                    'record_count': record_count
                }

                await exchange.publish(
                    aio_pika.Message(
                        body=json.dumps(message_data).encode(),
                        content_type='application/json',
                        message_id=message_data['message_id'],
                        correlation_id=message_data['correlation_id']
                    ),
                    routing_key=f"health.processing.{record_type}.normal"
                )
                print(f"  ✅ Published to RabbitMQ: message_id={message_data['message_id']}")
                print(f"     Records: {record_count}, Size: {len(file_content)} bytes\n")

            except Exception as e:
                print(f"  ❌ Failed: {e}\n")

        await connection.close()

    print(f"{'='*60}")
    print(f"Direct injection complete")
    print(f"{'='*60}\n")


def get_sample_files(record_type: str = None) -> List[Path]:
    """Get list of sample files to load"""
    if not SAMPLE_FILES_DIR.exists():
        print(f"❌ Sample files directory not found: {SAMPLE_FILES_DIR}")
        print(f"   Make sure you're running from the project root")
        sys.exit(1)

    if record_type:
        pattern = f"{record_type}_*.avro"
    else:
        pattern = "*.avro"

    files = list(SAMPLE_FILES_DIR.glob(pattern))
    files.sort()

    if not files:
        print(f"❌ No sample files found matching pattern: {pattern}")
        sys.exit(1)

    return files


async def main():
    parser = argparse.ArgumentParser(
        description="Load sample Avro files for ETL testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load all files via direct injection
  python scripts/load_sample_data.py --mode direct --all

  # Load specific record type
  python scripts/load_sample_data.py --mode direct --record-type BloodGlucoseRecord

  # Load via Health API (requires authentication)
  python scripts/load_sample_data.py --mode api --all --auth-token YOUR_TOKEN
        """
    )

    parser.add_argument(
        '--mode',
        choices=['api', 'direct'],
        default='direct',
        help='Loading mode: api (via Health API) or direct (MinIO+RabbitMQ)'
    )
    parser.add_argument(
        '--record-type',
        help='Specific record type to load (e.g., BloodGlucoseRecord)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Load all sample files'
    )
    parser.add_argument(
        '--user-id',
        default='sample_data_user',
        help='User ID for uploads (default: sample_data_user)'
    )
    parser.add_argument(
        '--auth-token',
        help='Auth token for API mode (required if mode=api)'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.all and not args.record_type:
        parser.error("Must specify either --all or --record-type")

    if args.mode == 'api' and not args.auth_token:
        parser.error("--auth-token required for API mode")

    # Get files to load
    files = get_sample_files(args.record_type)

    print(f"\n{'='*60}")
    print(f"ETL Sample Data Loader")
    print(f"{'='*60}")
    print(f"Mode: {args.mode}")
    print(f"Files to load: {len(files)}")
    print(f"User ID: {args.user_id}")
    print(f"{'='*60}\n")

    # Load files
    if args.mode == 'api':
        await load_via_api(files, args.auth_token)
    else:
        await load_via_direct_injection(files, args.user_id)

    print(f"✅ Successfully loaded {len(files)} sample file(s)!\n")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
```

---

## Appendix B: Sample Data Statistics

### Complete Sample Dataset Overview

**Total Dataset:**
- **Files**: 26 files
- **Total Size**: ~200 KB
- **Coverage**: All 6 supported health data types
- **Purpose**: Comprehensive local development and testing

### Detailed Breakdown

**Blood Glucose Records:**
- **Files**: 5
- **Largest file**: 38,664 bytes
- **Smallest file**: 38,370 bytes
- **Estimated records per file**: ~200-300 glucose readings
- **Total estimated records**: ~1,200
- **Clinical value**: Highest - critical for diabetes management

**Heart Rate Records:**
- **Files**: 5
- **Average file size**: ~14,000 bytes
- **Range**: 13,146 - 15,692 bytes
- **Estimated records per file**: ~100-150 heart rate samples
- **Total estimated records**: ~600
- **Clinical value**: High - cardiovascular fitness indicator

**Sleep Session Records:**
- **Files**: 5
- **Average file size**: ~3,200 bytes
- **Range**: 2,532 - 4,156 bytes
- **Estimated records per file**: ~3-5 sleep sessions
- **Total estimated records**: ~20
- **Clinical value**: High - foundational for holistic health

**Steps Records:**
- **Files**: 5
- **Average file size**: ~1,300 bytes
- **Range**: 1,197 - 1,364 bytes
- **Estimated records per file**: ~5-10 daily step counts
- **Total estimated records**: ~40
- **Clinical value**: Medium - activity tracking

**Active Calories Burned Records:**
- **Files**: 3
- **Average file size**: ~1,300 bytes
- **Estimated records per file**: ~5-10 calorie entries
- **Total estimated records**: ~20
- **Clinical value**: Medium - exercise quantification

**Heart Rate Variability (RMSSD) Records:**
- **Files**: 3
- **Average file size**: ~13,400 bytes
- **Estimated records per file**: ~100 HRV measurements
- **Total estimated records**: ~300
- **Clinical value**: Medium - advanced fitness and stress metric

### Coverage Assessment

✅ **Excellent coverage for:**
- Blood Glucose (5 files, multiple scenarios)
- Heart Rate (5 files, various activities)
- Sleep (5 files, different sleep patterns)
- Steps (5 files, activity levels)

⚠️ **Adequate coverage for:**
- Active Calories (3 files - could add more for edge cases)
- HRV (3 files - could add more for variability)

**Recommendation**: The existing sample dataset is **sufficient** for MVP development and testing. Additional samples can be collected during beta testing with real users.

---

## Appendix C: Error Classification Taxonomy

### Error Types and Handling Strategy

| Error Type | Category | Retriable | Retry Delay | Max Retries | Final Action |
|------------|----------|-----------|-------------|-------------|--------------|
| **Network Errors** |
| S3 download timeout | NETWORK_ERROR | Yes | 30s, 5m, 15m | 3 | DLQ + Alert |
| S3 connection refused | NETWORK_ERROR | Yes | 30s, 5m | 2 | DLQ + Alert |
| RabbitMQ connection lost | NETWORK_ERROR | Yes | 10s, 30s | 3 | Reconnect + Requeue |
| **Storage Errors** |
| S3 object not found | DATA_ERROR | No | N/A | 0 | DLQ (likely upstream issue) |
| S3 access denied | AUTH_ERROR | No | N/A | 0 | DLQ + Critical Alert |
| S3 rate limit exceeded | RATE_LIMIT | Yes | 60s, 5m | 2 | DLQ if persistent |
| **Data Validation Errors** |
| Invalid Avro schema | SCHEMA_ERROR | No | N/A | 0 | Quarantine + Metadata |
| Low data quality score | DATA_QUALITY | No | N/A | 0 | Quarantine + Metadata |
| Missing required fields | SCHEMA_ERROR | No | N/A | 0 | Quarantine + Metadata |
| Physiological range violation | DATA_QUALITY | No | N/A | 0 | Quarantine (if severe) |
| **Processing Errors** |
| Processor logic exception | PROCESSING_ERROR | No | N/A | 0 | DLQ + Alert |
| Memory exhaustion (OOM) | RESOURCE_ERROR | Yes | 2m, 10m | 2 | DLQ + Scale Alert |
| Processing timeout | TIMEOUT_ERROR | Yes | 1m, 5m | 2 | DLQ if persistent |
| **System Errors** |
| Deduplication store unavailable | SYSTEM_ERROR | Yes | 30s, 2m | 3 | Critical Alert |
| Metrics endpoint failure | SYSTEM_ERROR | No | N/A | 0 | Log warning, continue |

### Error Recovery Flow

```
Error Detected
     │
     ├─ Is Retriable?
     │   │
     │   ├─ Yes ──▶ retry_count < max_retries?
     │   │            │
     │   │            ├─ Yes ──▶ Delay (exponential backoff) ──▶ Retry
     │   │            │
     │   │            └─ No ──▶ Dead Letter Queue + Alert
     │   │
     │   └─ No ──▶ Error Type?
     │              │
     │              ├─ DATA_QUALITY / SCHEMA ──▶ Quarantine + Metadata
     │              │
     │              └─ Other ──▶ Dead Letter Queue + Alert
```

---

## References

### Internal Documentation
- **Data Lake Service**: `services/data-lake/implementation_plan.md`
- **Message Queue Service**: `services/message-queue/implementation_plan.md`
- **Health API Service**: `services/health-api-service/implementation_plan.md`
- **Platform Architecture**: `docs/architecture/implementation_plan_optimal_hybrid.md`
- **Project Guidelines**: `CLAUDE.md`

### External Resources

**Health Data Standards:**
- Android Health Connect: https://developer.android.com/health-and-fitness/guides/health-connect
- FHIR Specification: https://www.hl7.org/fhir/
- Apache Avro Specification: https://avro.apache.org/docs/current/spec.html

**Clinical Guidelines:**
- ADA Diabetes Standards: https://diabetesjournals.org/care/issue/46/Supplement_1
- American Heart Association Target Heart Rates: https://www.heart.org/en/healthy-living/fitness/fitness-basics/target-heart-rates
- National Sleep Foundation Guidelines: https://www.sleepfoundation.org/

**Technology Documentation:**
- RabbitMQ: https://www.rabbitmq.com/documentation.html
- MinIO: https://min.io/docs/minio/linux/index.html
- FastAPI: https://fastapi.tiangolo.com/
- Pydantic: https://docs.pydantic.dev/
- Prometheus: https://prometheus.io/docs/
- Jaeger: https://www.jaegertracing.io/docs/

**AI/ML Resources:**
- MLflow: https://mlflow.org/docs/latest/index.html
- Instruction Fine-tuning: https://huggingface.co/docs/transformers/tasks/instruction_tuning

---

**Document Status:** ✅ Ready for Implementation
**Version:** 3.0 (Merged from v1.0 and v2.0)
**Next Steps:**
1. Review merged specification
2. Begin Week 1 implementation tasks
3. Set up local development environment
4. Load sample data and verify infrastructure

**Maintenance:** This document should be updated as implementation progresses and decisions are made.

---

*End of Specification Document v3.0*
