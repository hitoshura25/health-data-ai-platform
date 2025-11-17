# Data Validation Module (Module 2)

## Overview

This module implements comprehensive data validation and quality assessment for health data files. It validates Avro schemas, checks physiological ranges, assesses data completeness, and assigns quality scores. Low-quality data is automatically quarantined with detailed metadata.

## Module Status

✅ **COMPLETED** - Module 2 Implementation

### Implemented Components

- ✅ `ValidationResult` dataclass
- ✅ `DataQualityValidator` class with all validation checks
- ✅ `ValidationConfig` with pydantic settings
- ✅ Clinical ranges for all 6 health record types
- ✅ Schema validation
- ✅ Completeness checking
- ✅ Physiological range validation
- ✅ Temporal consistency checking
- ✅ Quality score calculation
- ✅ Quarantine mechanism with S3 integration
- ✅ Comprehensive unit tests (test_validation.py)
- ✅ Integration tests with real Avro samples (test_validation_integration.py)

## Architecture

```
validation/
├── __init__.py              # Public API exports
├── clinical_ranges.py       # Physiological range definitions
├── config.py                # Validation configuration
├── data_quality.py          # Main validation logic
└── README.md                # This file
```

## Usage

### Basic Validation

```python
from validation import DataQualityValidator, ValidationConfig

# Create validator with default settings
validator = DataQualityValidator()

# Validate records
result = await validator.validate(
    records=parsed_avro_records,
    record_type='BloodGlucoseRecord',
    file_size_bytes=38664
)

# Check result
if result.is_valid:
    print(f"Quality score: {result.quality_score:.2f}")
else:
    print(f"Validation failed: {result.errors}")
```

### Custom Configuration

```python
from validation import DataQualityValidator, ValidationConfig

# Custom configuration
config = ValidationConfig(
    quality_threshold=0.8,           # Higher threshold
    schema_weight=0.4,                # More weight on schema
    completeness_weight=0.3,
    physiological_weight=0.2,
    temporal_weight=0.1,
    enable_quarantine=True
)

validator = DataQualityValidator(config=config)
```

### Quarantine Low-Quality Files

```python
from validation import DataQualityValidator

# Create validator with S3 client
validator = DataQualityValidator(
    s3_client=s3_client,
    bucket_name='health-data'
)

# Validate
result = await validator.validate(records, record_type, file_size)

# Quarantine if invalid
if not result.is_valid:
    await validator.quarantine_file(
        s3_key='raw/BloodGlucoseRecord/2025/11/15/file.avro',
        validation_result=result,
        file_content=file_bytes
    )
```

### Check Clinical Ranges

```python
from validation import get_clinical_range, is_value_in_range

# Get range for a field
range_tuple = get_clinical_range('BloodGlucoseRecord', 'glucose_mg_dl')
print(f"Valid range: {range_tuple}")  # (20, 600)

# Check if value is in range
is_valid = is_value_in_range(100, 'BloodGlucoseRecord', 'glucose_mg_dl')
print(f"Value in range: {is_valid}")  # True
```

## Validation Checks

### 1. Schema Validation

Validates that required fields are present for each record type:

- **BloodGlucoseRecord**: `level`, `time`
- **HeartRateRecord**: `samples`, `time`
- **SleepSessionRecord**: `startTime`, `endTime`
- **StepsRecord**: `count`, `startTime`, `endTime`
- **ActiveCaloriesBurnedRecord**: `energy`, `startTime`, `endTime`
- **HeartRateVariabilityRmssdRecord**: `heartRateVariabilityRmssd`, `time`

### 2. Completeness Check

Calculates the percentage of required fields that are present and non-null across all records.

Score: `(fields_present / required_fields)` averaged across all records

### 3. Physiological Range Validation

Checks that values fall within medically plausible ranges:

| Record Type | Field | Min | Max |
|------------|-------|-----|-----|
| BloodGlucoseRecord | glucose_mg_dl | 20 | 600 |
| HeartRateRecord | heart_rate_bpm | 30 | 220 |
| SleepSessionRecord | duration_hours | 0.5 | 16 |
| StepsRecord | count | 0 | 100,000 |
| ActiveCaloriesBurnedRecord | calories | 0 | 10,000 |
| HeartRateVariabilityRmssdRecord | rmssd_ms | 1 | 300 |

### 4. Temporal Consistency

Verifies that timestamps are in chronological order.

- Score: 1.0 if sorted, 0.7 if not sorted

### 5. Quality Score Calculation

```
quality_score = (
    0.3 × schema_validity_score +
    0.3 × completeness_score +
    0.2 × physiological_validity_score +
    0.2 × temporal_consistency_score
)
```

**Decision Threshold**: Default 0.7

- `quality_score >= 0.7` → Valid (process normally)
- `quality_score < 0.7` → Invalid (quarantine)

## ValidationResult

The `ValidationResult` dataclass contains:

```python
@dataclass
class ValidationResult:
    is_valid: bool                    # Overall validation status
    errors: List[str]                 # Blocking errors
    warnings: List[str]               # Non-blocking warnings
    quality_score: float              # 0.0 to 1.0
    metadata: Dict[str, Any]          # Additional validation metadata
```

### Metadata Fields

- `schema_valid`: Boolean indicating schema validity
- `completeness_score`: 0.0 to 1.0
- `physiological_score`: 0.0 to 1.0
- `temporal_score`: 0.0 to 1.0
- `record_count`: Number of records validated
- `record_type`: Type of health record

## Quarantine Mechanism

When a file fails validation, it is quarantined with metadata:

### S3 Structure

```
quarantine/
├── BloodGlucoseRecord/
│   └── 2025/11/15/
│       ├── user123_1731628800_abc123.avro
│       └── user123_1731628800_abc123.avro.metadata.json
```

### Metadata File Content

```json
{
  "original_key": "raw/BloodGlucoseRecord/2025/11/15/user123_1731628800_abc123.avro",
  "quarantine_reason": ["Quality score 0.45 below threshold 0.70"],
  "quality_score": 0.45,
  "warnings": ["Data completeness below optimal: 0.62"],
  "quarantined_at": "2025-11-17T10:30:00.000000",
  "validation_metadata": {
    "schema_valid": true,
    "completeness_score": 0.62,
    "physiological_score": 0.85,
    "temporal_score": 0.70,
    "record_count": 24,
    "record_type": "BloodGlucoseRecord"
  }
}
```

## Running Tests

### Unit Tests

```bash
# From service directory
pytest tests/test_validation.py -v
```

### Integration Tests (requires sample files)

```bash
# From service directory
pytest tests/test_validation_integration.py -v -m integration
```

### Coverage Report

```bash
pytest tests/test_validation.py --cov=src/validation --cov-report=html
```

## Dependencies

All dependencies are already in `requirements.txt`:

- `pydantic==2.11.9` - Data validation
- `pydantic-settings==2.11.0` - Configuration
- `aioboto3==12.3.0` - S3 for quarantine
- `fastavro==1.9.3` - For integration tests
- `structlog==24.1.0` - Logging

## Integration with Other Modules

### Module 1 (Consumer) Integration

```python
# Module 1 calls validation after parsing Avro
validator = DataQualityValidator(quality_threshold=0.7)
validation_result = await validator.validate(records, record_type, file_size)

if not validation_result.is_valid:
    # Quarantine file
    await validator.quarantine_file(s3_key, validation_result, file_content)
    return

# Continue processing...
```

### Module 3 (Processors) Integration

```python
# Module 3 receives validation result for context
processing_result = await processor.process_with_clinical_insights(
    records,
    message_data,
    validation_result  # ← Used for context
)
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `quality_threshold` | 0.7 | Minimum quality score for valid data |
| `enable_quarantine` | True | Enable quarantine for low-quality data |
| `schema_weight` | 0.3 | Weight for schema validation |
| `completeness_weight` | 0.3 | Weight for completeness |
| `physiological_weight` | 0.2 | Weight for physiological ranges |
| `temporal_weight` | 0.2 | Weight for temporal consistency |
| `max_file_size_mb` | 100 | Maximum file size |
| `max_records_per_file` | 100,000 | Maximum records per file |
| `quarantine_prefix` | "quarantine/" | S3 prefix for quarantined files |
| `include_quarantine_metadata` | True | Include metadata file |

## Performance

- Validation should complete in <1 second for 10,000 records
- Optimized for streaming validation
- Minimal memory footprint

## Future Enhancements

1. **Custom Validation Rules**: Allow per-client custom validation
2. **Quarantine Review UI**: Admin interface to review quarantined files
3. **Machine Learning**: Anomaly detection for unusual patterns
4. **Configurable Ranges**: Per-user physiological ranges based on medical history
5. **Audit Logging**: Detailed audit trail for validation decisions

## Success Criteria

✅ All 6 health data types have validation rules defined
✅ Quality score calculation working and tested
✅ Quarantine mechanism uploads files + metadata to S3
✅ Physiological ranges defined for all data types
✅ Temporal consistency checking works
✅ Unit tests: >80% coverage
✅ Integration tests with real sample files passing
✅ Documentation complete with examples

## Module Complete

Module 2 (Data Validation & Quality Framework) is **COMPLETE** and ready for integration with Module 1 (Core Consumer) and Module 3 (Clinical Processors).
