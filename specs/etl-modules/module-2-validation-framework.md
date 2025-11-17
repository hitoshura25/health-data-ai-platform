# Module 2: Data Validation & Quality Framework

**Module ID:** ETL-M2
**Priority:** P0 (Foundation - Needed by all processors)
**Estimated Effort:** 1 week
**Dependencies:** None (can start immediately)
**Team Assignment:** Data Engineer or Backend Developer

---

## Module Overview

This module implements comprehensive data validation and quality assessment for health data files. It validates Avro schemas, checks physiological ranges, assesses data completeness, and assigns quality scores. Low-quality data is automatically quarantined with detailed metadata.

### Key Responsibilities
- Avro schema validation
- Physiological range validation
- Data completeness checking
- Temporal consistency validation
- Quality score calculation
- Quarantine mechanism for low-quality data

### What This Module Does NOT Include
- ❌ Message consumption (Module 1)
- ❌ Clinical processing (Module 3)
- ❌ Training data generation (Module 4)

---

## Interfaces Provided

### **1. Validation Interface**

```python
# src/validation/data_quality.py
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class ValidationResult:
    """Result of data quality validation"""
    is_valid: bool                  # Overall validation status
    errors: List[str]               # Blocking errors
    warnings: List[str]             # Non-blocking warnings
    quality_score: float            # 0.0 to 1.0
    metadata: Dict[str, Any]        # Additional validation metadata

class DataQualityValidator:
    """Interface for data quality validation"""

    async def validate(
        self,
        records: List[Dict],
        record_type: str,
        file_size_bytes: int
    ) -> ValidationResult:
        """
        Validate health data records

        Args:
            records: List of parsed Avro records
            record_type: Type of health data (e.g., "BloodGlucoseRecord")
            file_size_bytes: Size of original file

        Returns:
            ValidationResult with quality assessment
        """
        pass
```

**Contract:**
- Consumer (Module 1) calls this after parsing Avro file
- Returns `ValidationResult` with quality score
- If `is_valid == False`, consumer should quarantine
- If `is_valid == True but quality_score < threshold`, may still quarantine
- Processors (Module 3) receive `ValidationResult` for context

### **2. Clinical Range Definitions**

```python
# src/validation/clinical_ranges.py
from typing import Dict, Tuple

# Physiological ranges (extreme but possible values)
CLINICAL_RANGES: Dict[str, Dict[str, Tuple[float, float]]] = {
    'BloodGlucoseRecord': {
        'glucose_mg_dl': (20, 600),  # Extreme hypo to extreme hyper
    },
    'HeartRateRecord': {
        'heart_rate_bpm': (30, 220),  # Extreme bradycardia to tachycardia
    },
    'SleepSessionRecord': {
        'duration_hours': (0.5, 16),  # Min nap to max sleep
    },
    'StepsRecord': {
        'count': (0, 100000),
    },
    'ActiveCaloriesBurnedRecord': {
        'calories': (0, 10000),
    },
    'HeartRateVariabilityRmssdRecord': {
        'rmssd_ms': (1, 300),
    }
}

def get_clinical_range(record_type: str, field: str) -> Tuple[float, float] | None:
    """Get clinical range for a specific field"""
    return CLINICAL_RANGES.get(record_type, {}).get(field)
```

---

## Technical Specifications

### 1. Quality Scoring Formula

```python
quality_score = (
    0.3 * schema_validity_score +      # Schema compliance
    0.3 * completeness_score +          # Required fields present
    0.2 * physiological_validity_score + # Values in range
    0.2 * temporal_consistency_score    # Chronological order
)

# Scoring:
# schema_validity_score: 1.0 if valid schema, 0.0 if invalid
# completeness_score: (fields_present / required_fields)
# physiological_validity_score: (values_in_range / total_values)
# temporal_consistency_score: 1.0 if chronological, 0.7 if not

# Decision:
# quality_score >= 0.7 → Valid (process normally)
# quality_score < 0.7 → Invalid (quarantine if enabled)
```

### 2. Validation Checks

#### **Schema Validation**
```python
async def _validate_schema(
    self,
    records: List[Dict],
    record_type: str
) -> bool:
    """Validate Avro schema compliance"""

    if not records:
        return False

    # Define required fields per record type
    required_fields = {
        'BloodGlucoseRecord': ['level', 'time'],
        'HeartRateRecord': ['samples', 'time'],
        'SleepSessionRecord': ['startTime', 'endTime'],
        'StepsRecord': ['count', 'startTime', 'endTime'],
        'ActiveCaloriesBurnedRecord': ['energy', 'startTime', 'endTime'],
        'HeartRateVariabilityRmssdRecord': ['heartRateVariabilityRmssd', 'time']
    }

    fields = required_fields.get(record_type, [])
    if not fields:
        return True  # Unknown type, assume valid

    # Check first record has required structure
    first_record = records[0]
    return all(field in first_record for field in fields)
```

#### **Completeness Check**
```python
async def _check_completeness(
    self,
    records: List[Dict],
    record_type: str
) -> float:
    """Check data completeness (0.0 to 1.0)"""

    if not records:
        return 0.0

    required_fields = self._get_required_fields(record_type)
    if not required_fields:
        return 1.0

    complete_count = 0
    for record in records:
        fields_present = sum(
            1 for field in required_fields
            if field in record and record[field] is not None
        )
        complete_count += fields_present / len(required_fields)

    return complete_count / len(records)
```

#### **Physiological Range Validation**
```python
async def _check_physiological_ranges(
    self,
    records: List[Dict],
    record_type: str
) -> float:
    """Check values are within physiological ranges (0.0 to 1.0)"""

    range_config = {
        'BloodGlucoseRecord': {
            'field_path': 'level.inMilligramsPerDeciliter',
            'min': 20,
            'max': 600
        },
        'HeartRateRecord': {
            'field_path': 'samples[0].beatsPerMinute',  # Check first sample
            'min': 30,
            'max': 220
        }
    }

    config = range_config.get(record_type)
    if not config:
        return 1.0  # No validation defined, assume valid

    valid_count = 0
    total_count = 0

    for record in records:
        value = self._get_nested_field(record, config['field_path'])
        if value is not None:
            total_count += 1
            if config['min'] <= value <= config['max']:
                valid_count += 1

    return valid_count / total_count if total_count > 0 else 0.0
```

#### **Temporal Consistency**
```python
async def _check_temporal_consistency(
    self,
    records: List[Dict]
) -> float:
    """Check timestamps are in chronological order (0.0 to 1.0)"""

    if len(records) < 2:
        return 1.0

    # Extract timestamps
    timestamps = []
    for record in records:
        time_field = record.get('time', {})
        if 'epochMillis' in time_field:
            timestamps.append(time_field['epochMillis'])
        elif 'startTime' in record:
            start_time = record['startTime']
            if isinstance(start_time, dict) and 'epochMillis' in start_time:
                timestamps.append(start_time['epochMillis'])

    if len(timestamps) < 2:
        return 1.0

    # Check if sorted
    is_sorted = all(
        timestamps[i] <= timestamps[i+1]
        for i in range(len(timestamps)-1)
    )

    return 1.0 if is_sorted else 0.7  # Partial credit if not sorted
```

### 3. Quarantine Mechanism

**When to Quarantine:**
- `quality_score < threshold` (default: 0.7)
- Blocking errors in validation
- Invalid Avro schema

**Quarantine Process:**
```python
async def quarantine_file(
    self,
    s3_key: str,
    validation_result: ValidationResult,
    file_content: bytes
) -> None:
    """Move file to quarantine with metadata"""

    # Generate quarantine key
    quarantine_key = s3_key.replace('raw/', 'quarantine/')

    # Upload quarantined file
    await self.s3_client.put_object(
        bucket=self.bucket_name,
        key=quarantine_key,
        body=file_content,
        content_type='application/avro'
    )

    # Create metadata file
    metadata = {
        'original_key': s3_key,
        'quarantine_reason': validation_result.errors,
        'quality_score': validation_result.quality_score,
        'warnings': validation_result.warnings,
        'quarantined_at': datetime.utcnow().isoformat(),
        'validation_metadata': validation_result.metadata
    }

    await self.s3_client.put_object(
        bucket=self.bucket_name,
        key=f"{quarantine_key}.metadata.json",
        body=json.dumps(metadata, indent=2).encode(),
        content_type='application/json'
    )
```

**Quarantine S3 Structure:**
```
quarantine/
├── BloodGlucoseRecord/
│   └── 2025/11/15/
│       ├── user123_1731628800_abc123.avro
│       └── user123_1731628800_abc123.avro.metadata.json
└── HeartRateRecord/
    └── 2025/11/15/
        ├── user456_1731628900_def456.avro
        └── user456_1731628900_def456.avro.metadata.json
```

---

## Implementation Checklist

### Week 1: Core Validation
- [ ] Create validation module structure
- [ ] Implement `ValidationResult` dataclass
- [ ] Implement `DataQualityValidator` class
- [ ] Implement schema validation
  - [ ] Define required fields per record type
  - [ ] Validate field presence
- [ ] Implement completeness checking
  - [ ] Calculate completeness score
  - [ ] Handle missing fields gracefully
- [ ] Implement physiological range validation
  - [ ] Define ranges for all 6 record types
  - [ ] Nested field extraction utility
  - [ ] Range checking logic
- [ ] Implement temporal consistency check
  - [ ] Timestamp extraction (handle multiple formats)
  - [ ] Chronological order verification
- [ ] Implement quality scoring
  - [ ] Weighted score calculation
  - [ ] Threshold configuration
- [ ] Implement quarantine mechanism
  - [ ] S3 quarantine upload
  - [ ] Metadata generation
- [ ] Write unit tests (>80% coverage)
- [ ] Write integration tests

---

## Testing Strategy

### Unit Tests

```python
# tests/test_validation.py
@pytest.mark.asyncio
async def test_quality_score_calculation():
    """Test quality score formula"""
    validator = DataQualityValidator(quality_threshold=0.7)

    # Perfect data
    records = create_perfect_glucose_records()
    result = await validator.validate(records, 'BloodGlucoseRecord', 38664)

    assert result.is_valid is True
    assert result.quality_score >= 0.9
    assert len(result.errors) == 0

@pytest.mark.asyncio
async def test_low_quality_data_detected():
    """Test low quality data is detected"""
    validator = DataQualityValidator(quality_threshold=0.7)

    # Missing required fields
    records = create_incomplete_records()
    result = await validator.validate(records, 'BloodGlucoseRecord', 5000)

    assert result.is_valid is False
    assert result.quality_score < 0.7
    assert len(result.errors) > 0 or len(result.warnings) > 0

@pytest.mark.asyncio
async def test_physiological_range_violations():
    """Test out-of-range values are flagged"""
    validator = DataQualityValidator(quality_threshold=0.7)

    # Glucose value of 1000 mg/dL (impossible)
    records = create_records_with_extreme_values()
    result = await validator.validate(records, 'BloodGlucoseRecord', 10000)

    # Should have warnings about out-of-range values
    assert len(result.warnings) > 0
    assert result.metadata['physiological_score'] < 1.0

@pytest.mark.asyncio
async def test_quarantine_metadata_generation():
    """Test quarantine creates proper metadata"""
    validator = DataQualityValidator(quality_threshold=0.7)

    validation_result = ValidationResult(
        is_valid=False,
        errors=["Missing required field: level"],
        warnings=[],
        quality_score=0.5,
        metadata={'completeness_score': 0.5}
    )

    # Quarantine should create metadata file
    await validator.quarantine_file(
        s3_key="raw/BloodGlucoseRecord/2025/11/15/test.avro",
        validation_result=validation_result,
        file_content=b"test_data"
    )

    # Verify metadata file created
    metadata = await s3_client.get_object(
        bucket='health-data',
        key='quarantine/BloodGlucoseRecord/2025/11/15/test.avro.metadata.json'
    )
    metadata_json = json.loads(metadata)

    assert 'quarantine_reason' in metadata_json
    assert 'quality_score' in metadata_json
    assert metadata_json['quality_score'] == 0.5
```

### Integration Tests

```python
# tests/test_validation_integration.py
@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_validation_with_real_avro():
    """Test validation with actual sample files"""
    validator = DataQualityValidator(quality_threshold=0.7)

    # Load real sample file
    sample_file = "docs/sample-avro-files/BloodGlucoseRecord_1758407139312.avro"
    with open(sample_file, 'rb') as f:
        from fastavro import reader
        records = list(reader(f))

    result = await validator.validate(
        records,
        'BloodGlucoseRecord',
        os.path.getsize(sample_file)
    )

    # Sample files should pass validation
    assert result.is_valid is True
    assert result.quality_score >= 0.8
    assert len(result.errors) == 0
```

---

## Configuration

```python
# src/validation/config.py
from pydantic import BaseModel

class ValidationConfig(BaseModel):
    """Validation configuration"""

    # Quality thresholds
    quality_threshold: float = 0.7
    enable_quarantine: bool = True

    # Scoring weights
    schema_weight: float = 0.3
    completeness_weight: float = 0.3
    physiological_weight: float = 0.2
    temporal_weight: float = 0.2

    # File limits
    max_file_size_mb: int = 100
    max_records_per_file: int = 100000

    # Quarantine settings
    quarantine_prefix: str = "quarantine/"
    include_quarantine_metadata: bool = True
```

---

## Dependencies

### Python Packages
```txt
pydantic==2.5.0              # Data validation
pydantic-settings==2.1.0     # Configuration
aioboto3==12.3.0             # S3 for quarantine
fastavro==1.9.3              # For integration tests
structlog==24.1.0            # Logging
```

### External Services
- MinIO/S3 (for quarantine uploads)

---

## Success Criteria

**Module Complete When:**
- ✅ All 6 health data types have validation rules defined
- ✅ Quality score calculation working and tested
- ✅ Quarantine mechanism uploads files + metadata to S3
- ✅ Physiological ranges defined for all data types
- ✅ Temporal consistency checking works
- ✅ Unit tests: >80% coverage
- ✅ Integration tests with real sample files passing
- ✅ Documentation complete with examples

**Ready for Integration When:**
- ✅ `ValidationResult` dataclass is stable
- ✅ `DataQualityValidator` interface is final
- ✅ Clinical ranges are documented
- ✅ Modules 1 and 3 can integrate easily

---

## Integration Points

### **Depends On:**
- None (foundation module)

### **Depended On By:**
- **Module 1** (Core Consumer) - Calls validation after Avro parsing
- **Module 3** (Clinical Processors) - Receives validation result for context

### **Interface Contract:**
```python
# Module 1 calls validation like this:
validator = DataQualityValidator(quality_threshold=0.7)
validation_result = await validator.validate(records, record_type, file_size)

if not validation_result.is_valid:
    # Quarantine file
    await validator.quarantine_file(s3_key, validation_result, file_content)
    return

# Module 3 receives validation_result:
processing_result = await processor.process_with_clinical_insights(
    records, message_data, validation_result  # ← Passed to processor
)
```

---

## Notes & Considerations

1. **Clinical Range Updates**: Ranges may need adjustment based on real-world data. Make them configurable.

2. **Custom Validation Rules**: Future enhancement could allow custom validation rules per client/user.

3. **Quarantine Review**: Implement admin interface to review quarantined files (future).

4. **Performance**: Validation should complete in <1 second for 10,000 records.

5. **Extension Point**: Design allows adding new validation checks without breaking interface.

---

**End of Module 2 Specification**
