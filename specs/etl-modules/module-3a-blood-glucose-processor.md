# Module 3a: Blood Glucose Clinical Processor

**Module ID:** ETL-M3a
**Priority:** P1 (HIGH - Most Complex Clinical Processor)
**Estimated Effort:** 1 week
**Dependencies:** Module 1 (BaseClinicalProcessor interface), Module 2 (ValidationResult)
**Team Assignment:** Backend Developer with Clinical/Medical Domain Knowledge

---

## Module Overview

This module implements specialized clinical processing for blood glucose data from Android Health Connect. It analyzes glucose readings to identify clinically significant patterns, generates human-readable narratives, and provides structured clinical insights for AI model training.

### Key Responsibilities
- Parse BloodGlucoseRecord Avro files
- Classify glucose readings (hypoglycemia, normal, hyperglycemia)
- Identify glucose patterns (fasting, post-meal, overnight)
- Calculate glycemic variability metrics
- Generate clinical narratives
- Extract structured clinical insights

### What This Module Does NOT Include
- ❌ Message consumption (Module 1)
- ❌ Data validation (Module 2)
- ❌ Training data formatting (Module 4)
- ❌ Metrics collection (Module 5)

---

## Clinical Background

### Blood Glucose Ranges (mg/dL)

```python
# Clinical classification based on American Diabetes Association guidelines
GLUCOSE_RANGES = {
    'severe_hypoglycemia': (0, 54),      # Immediate intervention needed
    'hypoglycemia': (54, 70),            # Low, requires treatment
    'normal_fasting': (70, 100),         # Healthy fasting range
    'normal_general': (70, 140),         # General healthy range
    'prediabetes_fasting': (100, 126),   # Warning sign
    'hyperglycemia': (140, 180),         # Elevated
    'severe_hyperglycemia': (180, 600),  # Very high, medical attention
}

# Context-specific ranges
FASTING_TARGET = (70, 100)      # Before meals (>8 hours fasting)
POST_MEAL_TARGET = (70, 140)    # 1-2 hours after meals
BEDTIME_TARGET = (90, 150)      # Before sleep
```

### Glycemic Variability Metrics

**Coefficient of Variation (CV):**
- CV = (standard_deviation / mean) × 100
- Target: CV < 36% (stable glucose control)
- CV > 36%: High variability (poor control)

**Time in Range (TIR):**
- % of readings in target range (70-180 mg/dL)
- Excellent: >70% TIR
- Good: 50-70% TIR
- Poor: <50% TIR

---

## Interface Implementation

### **1. Processor Interface**

```python
# src/processors/blood_glucose_processor.py
from typing import List, Dict, Any
from datetime import datetime, timedelta
import statistics
from src.processors.base_processor import BaseClinicalProcessor, ProcessingResult
from src.validation.data_quality import ValidationResult

class BloodGlucoseProcessor(BaseClinicalProcessor):
    """Clinical processor for blood glucose data"""

    async def initialize(self):
        """Initialize glucose processor with clinical ranges"""
        self.ranges = {
            'severe_hypoglycemia': (0, 54),
            'hypoglycemia': (54, 70),
            'normal_fasting': (70, 100),
            'normal_general': (70, 140),
            'prediabetes_fasting': (100, 126),
            'hyperglycemia': (140, 180),
            'severe_hyperglycemia': (180, 600),
        }

        self.context_ranges = {
            'fasting': (70, 100),
            'post_meal': (70, 140),
            'bedtime': (90, 150),
        }

    async def process_with_clinical_insights(
        self,
        records: List[Dict[str, Any]],
        message_data: Dict[str, Any],
        validation_result: ValidationResult
    ) -> ProcessingResult:
        """
        Process glucose records and generate clinical narrative

        Args:
            records: Parsed BloodGlucoseRecord Avro records
            message_data: Metadata from RabbitMQ message
            validation_result: Result from Module 2 validation

        Returns:
            ProcessingResult with narrative and clinical insights
        """
        start_time = datetime.utcnow()

        try:
            # Extract glucose readings
            readings = self._extract_glucose_readings(records)

            if not readings:
                return ProcessingResult(
                    success=False,
                    error_message="No valid glucose readings found",
                    processing_time_seconds=0.0
                )

            # Classify each reading
            classifications = self._classify_readings(readings)

            # Identify patterns
            patterns = self._identify_patterns(readings, classifications)

            # Calculate variability metrics
            metrics = self._calculate_variability_metrics(readings)

            # Generate clinical narrative
            narrative = self._generate_narrative(
                readings, classifications, patterns, metrics
            )

            # Extract structured clinical insights
            clinical_insights = self._extract_clinical_insights(
                classifications, patterns, metrics
            )

            processing_time = (datetime.utcnow() - start_time).total_seconds()

            return ProcessingResult(
                success=True,
                narrative=narrative,
                processing_time_seconds=processing_time,
                records_processed=len(records),
                quality_score=validation_result.quality_score,
                clinical_insights=clinical_insights
            )

        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            return ProcessingResult(
                success=False,
                error_message=f"Glucose processing failed: {str(e)}",
                processing_time_seconds=processing_time
            )
```

---

## Technical Implementation

### 1. Glucose Reading Extraction

```python
def _extract_glucose_readings(
    self,
    records: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Extract glucose values and timestamps from Avro records"""

    readings = []

    for record in records:
        try:
            # Extract glucose level
            level = record.get('level', {})
            glucose_mg_dl = level.get('inMilligramsPerDeciliter')

            # Extract timestamp
            time_data = record.get('time', {})
            epoch_millis = time_data.get('epochMillis')

            # Extract meal context if available
            metadata = record.get('metadata', {})
            relation_to_meal = metadata.get('relationToMeal')

            # Extract specimen source (fingerstick vs CGM)
            specimen_source = record.get('specimenSource')

            if glucose_mg_dl is not None and epoch_millis is not None:
                readings.append({
                    'glucose_mg_dl': glucose_mg_dl,
                    'timestamp': datetime.fromtimestamp(epoch_millis / 1000),
                    'epoch_millis': epoch_millis,
                    'relation_to_meal': relation_to_meal,
                    'specimen_source': specimen_source,
                })

        except (KeyError, TypeError, ValueError) as e:
            # Skip malformed records
            continue

    # Sort by timestamp
    readings.sort(key=lambda x: x['timestamp'])

    return readings
```

### 2. Glucose Classification

```python
def _classify_readings(
    self,
    readings: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Classify each glucose reading"""

    classifications = []

    for reading in readings:
        glucose = reading['glucose_mg_dl']

        # Determine classification
        if glucose < 54:
            category = 'severe_hypoglycemia'
            severity = 'critical'
        elif glucose < 70:
            category = 'hypoglycemia'
            severity = 'warning'
        elif glucose <= 100:
            category = 'normal_fasting'
            severity = 'normal'
        elif glucose <= 140:
            category = 'normal_general'
            severity = 'normal'
        elif glucose <= 180:
            category = 'hyperglycemia'
            severity = 'warning'
        else:
            category = 'severe_hyperglycemia'
            severity = 'critical'

        classifications.append({
            'reading': reading,
            'category': category,
            'severity': severity,
            'glucose_mg_dl': glucose,
            'timestamp': reading['timestamp']
        })

    return classifications
```

### 3. Pattern Identification

```python
def _identify_patterns(
    self,
    readings: List[Dict[str, Any]],
    classifications: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Identify clinically significant glucose patterns"""

    patterns = {
        'hypoglycemic_events': [],
        'hyperglycemic_events': [],
        'fasting_readings': [],
        'post_meal_readings': [],
        'overnight_readings': [],
        'trends': None
    }

    # Identify hypoglycemic events
    for i, classification in enumerate(classifications):
        if classification['severity'] in ['warning', 'critical']:
            if classification['category'] in ['hypoglycemia', 'severe_hypoglycemia']:
                patterns['hypoglycemic_events'].append({
                    'timestamp': classification['timestamp'],
                    'glucose': classification['glucose_mg_dl'],
                    'severity': classification['category']
                })

    # Identify hyperglycemic events
    for classification in classifications:
        if classification['category'] in ['hyperglycemia', 'severe_hyperglycemia']:
            patterns['hyperglycemic_events'].append({
                'timestamp': classification['timestamp'],
                'glucose': classification['glucose_mg_dl'],
                'severity': classification['category']
            })

    # Identify fasting readings (early morning, 6-10 AM)
    for reading in readings:
        hour = reading['timestamp'].hour
        if 6 <= hour <= 10:
            patterns['fasting_readings'].append({
                'timestamp': reading['timestamp'],
                'glucose': reading['glucose_mg_dl']
            })

    # Identify post-meal readings (using relation_to_meal metadata)
    for reading in readings:
        if reading.get('relation_to_meal') in ['AFTER_MEAL', 'POSTPRANDIAL']:
            patterns['post_meal_readings'].append({
                'timestamp': reading['timestamp'],
                'glucose': reading['glucose_mg_dl']
            })

    # Identify overnight readings (10 PM - 6 AM)
    for reading in readings:
        hour = reading['timestamp'].hour
        if hour >= 22 or hour <= 6:
            patterns['overnight_readings'].append({
                'timestamp': reading['timestamp'],
                'glucose': reading['glucose_mg_dl']
            })

    # Identify trends (improving, worsening, stable)
    if len(readings) >= 5:
        patterns['trends'] = self._analyze_trends(readings)

    return patterns
```

### 4. Variability Metrics Calculation

```python
def _calculate_variability_metrics(
    self,
    readings: List[Dict[str, Any]]
) -> Dict[str, float]:
    """Calculate glycemic variability metrics"""

    if len(readings) < 2:
        return {'insufficient_data': True}

    glucose_values = [r['glucose_mg_dl'] for r in readings]

    # Mean glucose
    mean_glucose = statistics.mean(glucose_values)

    # Standard deviation
    std_dev = statistics.stdev(glucose_values) if len(glucose_values) > 1 else 0

    # Coefficient of Variation (CV)
    cv = (std_dev / mean_glucose * 100) if mean_glucose > 0 else 0

    # Time in Range (TIR) - 70-180 mg/dL
    in_range_count = sum(1 for g in glucose_values if 70 <= g <= 180)
    tir = (in_range_count / len(glucose_values)) * 100

    # Time below range (<70 mg/dL)
    below_range_count = sum(1 for g in glucose_values if g < 70)
    tbr = (below_range_count / len(glucose_values)) * 100

    # Time above range (>180 mg/dL)
    above_range_count = sum(1 for g in glucose_values if g > 180)
    tar = (above_range_count / len(glucose_values)) * 100

    return {
        'mean_glucose': round(mean_glucose, 1),
        'std_dev': round(std_dev, 1),
        'coefficient_of_variation': round(cv, 1),
        'time_in_range_percent': round(tir, 1),
        'time_below_range_percent': round(tbr, 1),
        'time_above_range_percent': round(tar, 1),
        'min_glucose': min(glucose_values),
        'max_glucose': max(glucose_values),
    }
```

### 5. Narrative Generation

```python
def _generate_narrative(
    self,
    readings: List[Dict[str, Any]],
    classifications: List[Dict[str, Any]],
    patterns: Dict[str, Any],
    metrics: Dict[str, float]
) -> str:
    """Generate clinical narrative from glucose data"""

    narrative_parts = []

    # Summary statement
    summary = self._generate_summary_statement(readings, metrics)
    narrative_parts.append(summary)

    # Variability assessment
    if 'coefficient_of_variation' in metrics:
        cv = metrics['coefficient_of_variation']
        tir = metrics['time_in_range_percent']

        if cv < 36 and tir >= 70:
            variability_text = (
                f"Glucose control is excellent with low variability (CV {cv}%) "
                f"and {tir}% time in target range (70-180 mg/dL)."
            )
        elif cv >= 36:
            variability_text = (
                f"Glucose variability is high (CV {cv}%), indicating unstable control. "
                f"Time in range is {tir}%."
            )
        else:
            variability_text = (
                f"Glucose variability is moderate (CV {cv}%) with {tir}% time in range."
            )

        narrative_parts.append(variability_text)

    # Hypoglycemic events
    hypo_events = patterns.get('hypoglycemic_events', [])
    if hypo_events:
        severe_hypo = [e for e in hypo_events if e['severity'] == 'severe_hypoglycemia']
        mild_hypo = [e for e in hypo_events if e['severity'] == 'hypoglycemia']

        if severe_hypo:
            narrative_parts.append(
                f"Alert: {len(severe_hypo)} severe hypoglycemic event(s) detected "
                f"(<54 mg/dL), requiring immediate intervention."
            )

        if mild_hypo:
            narrative_parts.append(
                f"{len(mild_hypo)} hypoglycemic reading(s) detected (54-70 mg/dL). "
                f"Consider adjusting medication or meal timing."
            )

    # Hyperglycemic events
    hyper_events = patterns.get('hyperglycemic_events', [])
    if hyper_events:
        severe_hyper = [e for e in hyper_events if e['severity'] == 'severe_hyperglycemia']
        mild_hyper = [e for e in hyper_events if e['severity'] == 'hyperglycemia']

        if severe_hyper:
            narrative_parts.append(
                f"{len(severe_hyper)} severe hyperglycemic reading(s) detected "
                f"(>180 mg/dL). Medication adjustment may be needed."
            )
        elif mild_hyper:
            narrative_parts.append(
                f"{len(mild_hyper)} elevated glucose reading(s) (140-180 mg/dL) observed."
            )

    # Fasting glucose assessment
    fasting_readings = patterns.get('fasting_readings', [])
    if fasting_readings:
        avg_fasting = statistics.mean([r['glucose'] for r in fasting_readings])

        if avg_fasting < 100:
            fasting_text = f"Fasting glucose is well-controlled (avg {avg_fasting:.0f} mg/dL)."
        elif avg_fasting <= 126:
            fasting_text = (
                f"Fasting glucose is elevated (avg {avg_fasting:.0f} mg/dL), "
                f"in prediabetes range (100-126 mg/dL)."
            )
        else:
            fasting_text = (
                f"Fasting glucose is significantly elevated (avg {avg_fasting:.0f} mg/dL), "
                f"consistent with diabetes (>126 mg/dL)."
            )

        narrative_parts.append(fasting_text)

    # Trend analysis
    trends = patterns.get('trends')
    if trends:
        narrative_parts.append(trends['description'])

    # Clinical recommendations
    recommendations = self._generate_recommendations(patterns, metrics)
    if recommendations:
        narrative_parts.append(f"Recommendations: {recommendations}")

    return " ".join(narrative_parts)
```

### 6. Clinical Insights Extraction

```python
def _extract_clinical_insights(
    self,
    classifications: List[Dict[str, Any]],
    patterns: Dict[str, Any],
    metrics: Dict[str, float]
) -> Dict[str, Any]:
    """Extract structured clinical insights for AI training"""

    # Count events by severity
    critical_events = sum(
        1 for c in classifications if c['severity'] == 'critical'
    )
    warning_events = sum(
        1 for c in classifications if c['severity'] == 'warning'
    )
    normal_events = sum(
        1 for c in classifications if c['severity'] == 'normal'
    )

    # Assess overall control
    if 'coefficient_of_variation' in metrics:
        cv = metrics['coefficient_of_variation']
        tir = metrics['time_in_range_percent']

        if cv < 36 and tir >= 70:
            control_status = 'excellent'
        elif cv < 36 and tir >= 50:
            control_status = 'good'
        elif tir >= 50:
            control_status = 'fair'
        else:
            control_status = 'poor'
    else:
        control_status = 'insufficient_data'

    return {
        'record_type': 'BloodGlucoseRecord',
        'total_readings': len(classifications),
        'critical_events': critical_events,
        'warning_events': warning_events,
        'normal_events': normal_events,
        'hypoglycemic_events_count': len(patterns.get('hypoglycemic_events', [])),
        'hyperglycemic_events_count': len(patterns.get('hyperglycemic_events', [])),
        'variability_metrics': metrics,
        'control_status': control_status,
        'fasting_readings_count': len(patterns.get('fasting_readings', [])),
        'post_meal_readings_count': len(patterns.get('post_meal_readings', [])),
        'overnight_readings_count': len(patterns.get('overnight_readings', [])),
        'trends': patterns.get('trends'),
    }
```

---

## Sample Narrative Output

**Input**: 450 glucose readings over 30 days

**Generated Narrative**:
```
Blood glucose data shows 450 readings over a 30-day period with mean glucose of
142.3 mg/dL. Glucose control is moderate with variability (CV 38%) and 62% time
in target range (70-180 mg/dL). Alert: 3 severe hypoglycemic events detected
(<54 mg/dL), requiring immediate intervention. 12 hypoglycemic readings detected
(54-70 mg/dL). Consider adjusting medication or meal timing. 45 elevated glucose
readings (140-180 mg/dL) observed. Fasting glucose is elevated (avg 118 mg/dL),
in prediabetes range (100-126 mg/dL). Glucose levels show improving trend over
the period with 15% reduction in hyperglycemic events. Recommendations: Review
medication timing to reduce hypoglycemic risk; monitor fasting glucose closely;
continue current management approach as trends are positive.
```

---

## Implementation Checklist

### Week 1: Blood Glucose Processor
- [ ] Create processor module structure
- [ ] Implement `BloodGlucoseProcessor` class
- [ ] Implement glucose reading extraction
  - [ ] Parse Avro BloodGlucoseRecord structure
  - [ ] Extract glucose values, timestamps, metadata
  - [ ] Handle missing/malformed data gracefully
- [ ] Implement glucose classification
  - [ ] Define clinical ranges
  - [ ] Classify each reading
  - [ ] Assign severity levels
- [ ] Implement pattern identification
  - [ ] Hypoglycemic event detection
  - [ ] Hyperglycemic event detection
  - [ ] Fasting glucose identification
  - [ ] Post-meal reading detection
  - [ ] Overnight pattern analysis
  - [ ] Trend analysis (improving/worsening/stable)
- [ ] Implement variability metrics
  - [ ] Mean glucose calculation
  - [ ] Standard deviation
  - [ ] Coefficient of variation
  - [ ] Time in range (TIR)
  - [ ] Time below range (TBR)
  - [ ] Time above range (TAR)
- [ ] Implement narrative generation
  - [ ] Summary statement generation
  - [ ] Variability assessment text
  - [ ] Hypoglycemic event descriptions
  - [ ] Hyperglycemic event descriptions
  - [ ] Fasting glucose assessment
  - [ ] Trend descriptions
  - [ ] Clinical recommendations
- [ ] Implement clinical insights extraction
  - [ ] Event counting by severity
  - [ ] Control status assessment
  - [ ] Structured metadata generation
- [ ] Write unit tests (>80% coverage)
- [ ] Write integration tests with sample files
- [ ] Document clinical logic and ranges

---

## Testing Strategy

### Unit Tests

```python
# tests/test_blood_glucose_processor.py
import pytest
from datetime import datetime, timedelta
from src.processors.blood_glucose_processor import BloodGlucoseProcessor
from src.validation.data_quality import ValidationResult

@pytest.fixture
async def processor():
    """Create glucose processor instance"""
    proc = BloodGlucoseProcessor()
    await proc.initialize()
    return proc

@pytest.mark.asyncio
async def test_extract_glucose_readings(processor):
    """Test extraction of glucose values from Avro records"""

    records = [
        {
            'level': {'inMilligramsPerDeciliter': 95.0},
            'time': {'epochMillis': 1700000000000},
            'metadata': {'relationToMeal': 'FASTING'},
            'specimenSource': 'FINGERSTICK'
        },
        {
            'level': {'inMilligramsPerDeciliter': 142.0},
            'time': {'epochMillis': 1700003600000},
            'metadata': {'relationToMeal': 'AFTER_MEAL'},
            'specimenSource': 'FINGERSTICK'
        }
    ]

    readings = processor._extract_glucose_readings(records)

    assert len(readings) == 2
    assert readings[0]['glucose_mg_dl'] == 95.0
    assert readings[1]['glucose_mg_dl'] == 142.0
    assert readings[0]['relation_to_meal'] == 'FASTING'

@pytest.mark.asyncio
async def test_classify_hypoglycemic_reading(processor):
    """Test classification of low glucose readings"""

    readings = [
        {
            'glucose_mg_dl': 62.0,
            'timestamp': datetime.utcnow(),
            'epoch_millis': 1700000000000
        }
    ]

    classifications = processor._classify_readings(readings)

    assert classifications[0]['category'] == 'hypoglycemia'
    assert classifications[0]['severity'] == 'warning'

@pytest.mark.asyncio
async def test_classify_severe_hypoglycemia(processor):
    """Test classification of severe hypoglycemia"""

    readings = [
        {
            'glucose_mg_dl': 48.0,
            'timestamp': datetime.utcnow(),
            'epoch_millis': 1700000000000
        }
    ]

    classifications = processor._classify_readings(readings)

    assert classifications[0]['category'] == 'severe_hypoglycemia'
    assert classifications[0]['severity'] == 'critical'

@pytest.mark.asyncio
async def test_variability_metrics_calculation(processor):
    """Test CV and TIR calculations"""

    # Create readings with known statistics
    readings = [
        {'glucose_mg_dl': 100.0, 'timestamp': datetime.utcnow()},
        {'glucose_mg_dl': 120.0, 'timestamp': datetime.utcnow()},
        {'glucose_mg_dl': 140.0, 'timestamp': datetime.utcnow()},
        {'glucose_mg_dl': 160.0, 'timestamp': datetime.utcnow()},
        {'glucose_mg_dl': 180.0, 'timestamp': datetime.utcnow()},
    ]

    metrics = processor._calculate_variability_metrics(readings)

    assert 'mean_glucose' in metrics
    assert 'coefficient_of_variation' in metrics
    assert 'time_in_range_percent' in metrics
    assert metrics['mean_glucose'] == 140.0
    assert metrics['time_in_range_percent'] == 100.0  # All in 70-180 range

@pytest.mark.asyncio
async def test_pattern_identification_hypoglycemia(processor):
    """Test identification of hypoglycemic events"""

    now = datetime.utcnow()
    readings = [
        {'glucose_mg_dl': 65.0, 'timestamp': now, 'epoch_millis': int(now.timestamp() * 1000)},
        {'glucose_mg_dl': 48.0, 'timestamp': now + timedelta(hours=1), 'epoch_millis': int((now + timedelta(hours=1)).timestamp() * 1000)},
        {'glucose_mg_dl': 95.0, 'timestamp': now + timedelta(hours=2), 'epoch_millis': int((now + timedelta(hours=2)).timestamp() * 1000)},
    ]

    classifications = processor._classify_readings(readings)
    patterns = processor._identify_patterns(readings, classifications)

    assert len(patterns['hypoglycemic_events']) == 2
    assert any(e['severity'] == 'severe_hypoglycemia' for e in patterns['hypoglycemic_events'])

@pytest.mark.asyncio
async def test_narrative_generation_normal_control(processor):
    """Test narrative for well-controlled glucose"""

    # Create 50 readings in normal range
    now = datetime.utcnow()
    readings = []
    for i in range(50):
        readings.append({
            'glucose_mg_dl': 90.0 + (i % 20),  # Values between 90-110
            'timestamp': now + timedelta(hours=i),
            'epoch_millis': int((now + timedelta(hours=i)).timestamp() * 1000),
            'relation_to_meal': None,
        })

    classifications = processor._classify_readings(readings)
    patterns = processor._identify_patterns(readings, classifications)
    metrics = processor._calculate_variability_metrics(readings)

    narrative = processor._generate_narrative(
        readings, classifications, patterns, metrics
    )

    assert 'well-controlled' in narrative.lower() or 'excellent' in narrative.lower()
    assert 'time in range' in narrative.lower()

@pytest.mark.asyncio
async def test_end_to_end_processing(processor):
    """Test complete processing pipeline"""

    # Simulate Avro records
    records = create_sample_glucose_avro_records()

    message_data = {
        'bucket': 'health-data',
        'key': 'raw/BloodGlucoseRecord/2025/11/test.avro',
        'record_type': 'BloodGlucoseRecord',
        'user_id': 'user123',
        'correlation_id': 'abc-def-123'
    }

    validation_result = ValidationResult(
        is_valid=True,
        errors=[],
        warnings=[],
        quality_score=0.95,
        metadata={}
    )

    result = await processor.process_with_clinical_insights(
        records, message_data, validation_result
    )

    assert result.success is True
    assert result.narrative is not None
    assert len(result.narrative) > 100
    assert result.clinical_insights is not None
    assert 'record_type' in result.clinical_insights
    assert result.clinical_insights['record_type'] == 'BloodGlucoseRecord'

def create_sample_glucose_avro_records() -> List[Dict]:
    """Helper to create realistic glucose records"""
    records = []
    base_time = datetime(2025, 11, 1, 6, 0, 0)

    for i in range(100):
        # Simulate realistic glucose pattern
        hour_offset = i * 2  # Reading every 2 hours
        timestamp = base_time + timedelta(hours=hour_offset)

        # Morning fasting: 80-100
        # Post-meal: 120-140
        # Overnight: 90-110
        hour = timestamp.hour
        if 6 <= hour <= 8:
            glucose = 80 + (i % 20)
        elif 12 <= hour <= 14:
            glucose = 120 + (i % 20)
        else:
            glucose = 90 + (i % 20)

        records.append({
            'level': {'inMilligramsPerDeciliter': glucose},
            'time': {'epochMillis': int(timestamp.timestamp() * 1000)},
            'metadata': {},
            'specimenSource': 'FINGERSTICK'
        })

    return records
```

### Integration Tests

```python
# tests/test_blood_glucose_integration.py
@pytest.mark.integration
@pytest.mark.asyncio
async def test_process_real_glucose_file():
    """Test processing with actual sample Avro file"""

    processor = BloodGlucoseProcessor()
    await processor.initialize()

    # Load real sample file
    sample_file = "docs/sample-avro-files/BloodGlucoseRecord_1758407139312.avro"

    with open(sample_file, 'rb') as f:
        from fastavro import reader
        records = list(reader(f))

    message_data = {
        'bucket': 'health-data',
        'key': 'raw/BloodGlucoseRecord/2025/11/real_sample.avro',
        'record_type': 'BloodGlucoseRecord',
        'user_id': 'integration_test',
        'correlation_id': 'test-123'
    }

    validation_result = ValidationResult(
        is_valid=True,
        errors=[],
        warnings=[],
        quality_score=0.9,
        metadata={}
    )

    result = await processor.process_with_clinical_insights(
        records, message_data, validation_result
    )

    # Verify successful processing
    assert result.success is True
    assert result.narrative is not None
    assert result.records_processed > 0

    # Verify clinical insights structure
    insights = result.clinical_insights
    assert 'total_readings' in insights
    assert 'variability_metrics' in insights
    assert 'control_status' in insights

    # Print narrative for manual review
    print("\n" + "="*80)
    print("GENERATED NARRATIVE:")
    print("="*80)
    print(result.narrative)
    print("="*80)
```

---

## Configuration

```python
# src/processors/glucose_config.py
from pydantic import BaseModel
from typing import Dict, Tuple

class GlucoseProcessorConfig(BaseModel):
    """Configuration for glucose processor"""

    # Clinical ranges (mg/dL)
    severe_hypoglycemia_threshold: float = 54.0
    hypoglycemia_threshold: float = 70.0
    normal_upper_limit: float = 140.0
    hyperglycemia_threshold: float = 180.0

    # Variability targets
    target_cv_percent: float = 36.0
    target_tir_percent: float = 70.0

    # Time-of-day ranges for fasting detection
    fasting_hour_start: int = 6
    fasting_hour_end: int = 10
    overnight_hour_start: int = 22
    overnight_hour_end: int = 6

    # Narrative generation
    include_recommendations: bool = True
    narrative_detail_level: str = "detailed"  # "brief", "detailed", "clinical"
```

---

## Dependencies

### Python Packages
```txt
# Already included in project
pydantic==2.5.0              # Data validation
pydantic-settings==2.1.0     # Configuration
fastavro==1.9.3              # Avro parsing (for tests)
structlog==24.1.0            # Logging
```

### External Services
- None (processor is pure compute, no external dependencies)

---

## Success Criteria

**Module Complete When:**
- ✅ Implements `BaseClinicalProcessor` interface
- ✅ Processes BloodGlucoseRecord Avro files correctly
- ✅ Classifies glucose readings accurately
- ✅ Identifies hypoglycemic and hyperglycemic events
- ✅ Calculates variability metrics (CV, TIR, etc.)
- ✅ Generates clinically accurate narratives
- ✅ Extracts structured clinical insights
- ✅ Unit tests: >80% coverage
- ✅ Integration tests with sample files passing
- ✅ Narratives reviewed by someone with clinical knowledge
- ✅ Documentation complete with clinical background

**Ready for Integration When:**
- ✅ ProcessorFactory can register BloodGlucoseProcessor
- ✅ Module 1 can call processor successfully
- ✅ Module 4 receives proper clinical_insights structure
- ✅ Performance: Processes 1000 readings in <3 seconds

---

## Integration Points

### **Depends On:**
- **Module 1** (Core Consumer) - Provides `BaseClinicalProcessor` interface
- **Module 2** (Validation) - Provides `ValidationResult`

### **Depended On By:**
- **Module 1** (Core Consumer) - Calls this processor for BloodGlucoseRecord
- **Module 4** (Training Data Output) - Receives narrative and clinical insights

### **Interface Contract:**
```python
# Module 1 calls processor like this:
from src.processors.processor_factory import ProcessorFactory

factory = ProcessorFactory()
processor = factory.get_processor('BloodGlucoseRecord')

result = await processor.process_with_clinical_insights(
    records=parsed_avro_records,
    message_data={
        'bucket': 'health-data',
        'key': 's3_key',
        'record_type': 'BloodGlucoseRecord',
        'user_id': 'user123',
        'correlation_id': 'abc-123'
    },
    validation_result=validation_result
)

# Module 4 receives:
if result.success:
    await training_formatter.generate_training_output(
        narrative=result.narrative,
        source_metadata={...},
        processing_metadata={
            'clinical_insights': result.clinical_insights,
            'quality_score': result.quality_score,
            ...
        }
    )
```

---

## Notes & Considerations

1. **Clinical Accuracy**: Glucose ranges are based on American Diabetes Association (ADA) guidelines. May need adjustment for specific populations or international guidelines.

2. **Contextual Processing**: Meal context (fasting, post-meal) significantly affects interpretation. Use `relationToMeal` metadata when available.

3. **CGM vs Fingerstick**: Continuous glucose monitors (CGM) provide more data points. Processing logic should handle both high-frequency CGM data and occasional fingerstick measurements.

4. **Narrative Tone**: Narratives should be informative but not prescriptive. Avoid making specific medical recommendations beyond general observations.

5. **Privacy**: Ensure narratives don't include PII. Only use aggregate statistics and clinical observations.

6. **Extension Points**: Design allows adding more sophisticated analysis:
   - Dawn phenomenon detection
   - Meal response patterns
   - Exercise impact analysis
   - Medication timing correlations

---

**End of Module 3a Specification**
