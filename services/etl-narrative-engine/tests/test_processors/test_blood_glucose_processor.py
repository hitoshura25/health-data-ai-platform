"""
Unit tests for Blood Glucose Clinical Processor.

Tests cover:
- Glucose reading extraction from Avro records
- Classification of glucose readings
- Pattern identification (hypo/hyperglycemia, fasting, overnight)
- Variability metrics calculation (CV, TIR)
- Narrative generation
- Clinical insights extraction
- End-to-end processing
"""

from datetime import datetime, timedelta

import pytest

from src.processors.blood_glucose_processor import BloodGlucoseProcessor
from src.validation.data_quality import ValidationResult


@pytest.fixture
async def processor():
    """Create glucose processor instance."""
    proc = BloodGlucoseProcessor()
    await proc.initialize()
    return proc


@pytest.mark.asyncio
async def test_processor_initialization(processor):
    """Test processor initializes with correct ranges."""
    assert processor.ranges is not None
    assert 'severe_hypoglycemia' in processor.ranges
    assert 'hyperglycemia' in processor.ranges
    assert processor.context_ranges is not None
    assert 'fasting' in processor.context_ranges


@pytest.mark.asyncio
async def test_extract_glucose_readings(processor):
    """Test extraction of glucose values from Avro records."""
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
    assert 'timestamp' in readings[0]


@pytest.mark.asyncio
async def test_extract_readings_with_malformed_data(processor):
    """Test extraction handles malformed records gracefully."""
    records = [
        {
            'level': {'inMilligramsPerDeciliter': 95.0},
            'time': {'epochMillis': 1700000000000},
            'metadata': {},
            'specimenSource': 'FINGERSTICK'
        },
        {
            # Missing level field
            'time': {'epochMillis': 1700003600000},
            'metadata': {},
        },
        {
            # Missing time field
            'level': {'inMilligramsPerDeciliter': 142.0},
            'metadata': {},
        },
        {
            # Valid record
            'level': {'inMilligramsPerDeciliter': 110.0},
            'time': {'epochMillis': 1700007200000},
            'metadata': {},
            'specimenSource': 'CGM'
        }
    ]

    readings = processor._extract_glucose_readings(records)

    # Should only extract valid records
    assert len(readings) == 2
    assert readings[0]['glucose_mg_dl'] == 95.0
    assert readings[1]['glucose_mg_dl'] == 110.0


@pytest.mark.asyncio
async def test_extract_readings_sorted_by_timestamp(processor):
    """Test readings are sorted chronologically."""
    records = [
        {
            'level': {'inMilligramsPerDeciliter': 120.0},
            'time': {'epochMillis': 1700003600000},  # Later time
            'metadata': {},
        },
        {
            'level': {'inMilligramsPerDeciliter': 95.0},
            'time': {'epochMillis': 1700000000000},  # Earlier time
            'metadata': {},
        }
    ]

    readings = processor._extract_glucose_readings(records)

    assert len(readings) == 2
    assert readings[0]['glucose_mg_dl'] == 95.0  # Earlier reading first
    assert readings[1]['glucose_mg_dl'] == 120.0


@pytest.mark.asyncio
async def test_classify_normal_fasting(processor):
    """Test classification of normal fasting glucose."""
    readings = [
        {
            'glucose_mg_dl': 85.0,
            'timestamp': datetime.utcnow(),
            'epoch_millis': 1700000000000
        }
    ]

    classifications = processor._classify_readings(readings)

    assert len(classifications) == 1
    assert classifications[0]['category'] == 'normal_fasting'
    assert classifications[0]['severity'] == 'normal'
    assert classifications[0]['glucose_mg_dl'] == 85.0


@pytest.mark.asyncio
async def test_classify_normal_general(processor):
    """Test classification of normal general glucose."""
    readings = [
        {
            'glucose_mg_dl': 120.0,
            'timestamp': datetime.utcnow(),
            'epoch_millis': 1700000000000
        }
    ]

    classifications = processor._classify_readings(readings)

    assert classifications[0]['category'] == 'normal_general'
    assert classifications[0]['severity'] == 'normal'


@pytest.mark.asyncio
async def test_classify_hypoglycemia(processor):
    """Test classification of low glucose readings."""
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
    """Test classification of severe hypoglycemia."""
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
async def test_classify_hyperglycemia(processor):
    """Test classification of high glucose readings."""
    readings = [
        {
            'glucose_mg_dl': 165.0,
            'timestamp': datetime.utcnow(),
            'epoch_millis': 1700000000000
        }
    ]

    classifications = processor._classify_readings(readings)

    assert classifications[0]['category'] == 'hyperglycemia'
    assert classifications[0]['severity'] == 'warning'


@pytest.mark.asyncio
async def test_classify_severe_hyperglycemia(processor):
    """Test classification of severe hyperglycemia."""
    readings = [
        {
            'glucose_mg_dl': 250.0,
            'timestamp': datetime.utcnow(),
            'epoch_millis': 1700000000000
        }
    ]

    classifications = processor._classify_readings(readings)

    assert classifications[0]['category'] == 'severe_hyperglycemia'
    assert classifications[0]['severity'] == 'critical'


@pytest.mark.asyncio
async def test_variability_metrics_calculation(processor):
    """Test CV and TIR calculations."""
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
    assert metrics['time_below_range_percent'] == 0.0
    assert metrics['time_above_range_percent'] == 0.0
    assert metrics['min_glucose'] == 100.0
    assert metrics['max_glucose'] == 180.0


@pytest.mark.asyncio
async def test_variability_metrics_with_outliers(processor):
    """Test metrics calculation with out-of-range values."""
    readings = [
        {'glucose_mg_dl': 50.0, 'timestamp': datetime.utcnow()},  # Below range
        {'glucose_mg_dl': 100.0, 'timestamp': datetime.utcnow()},
        {'glucose_mg_dl': 120.0, 'timestamp': datetime.utcnow()},
        {'glucose_mg_dl': 200.0, 'timestamp': datetime.utcnow()},  # Above range
    ]

    metrics = processor._calculate_variability_metrics(readings)

    assert metrics['time_in_range_percent'] == 50.0  # 2 out of 4
    assert metrics['time_below_range_percent'] == 25.0  # 1 out of 4
    assert metrics['time_above_range_percent'] == 25.0  # 1 out of 4


@pytest.mark.asyncio
async def test_variability_metrics_insufficient_data(processor):
    """Test metrics with insufficient data."""
    readings = [
        {'glucose_mg_dl': 100.0, 'timestamp': datetime.utcnow()},
    ]

    metrics = processor._calculate_variability_metrics(readings)

    assert 'insufficient_data' in metrics
    assert metrics['insufficient_data'] is True


@pytest.mark.asyncio
async def test_pattern_identification_hypoglycemia(processor):
    """Test identification of hypoglycemic events."""
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
    assert any(e['severity'] == 'hypoglycemia' for e in patterns['hypoglycemic_events'])


@pytest.mark.asyncio
async def test_pattern_identification_hyperglycemia(processor):
    """Test identification of hyperglycemic events."""
    now = datetime.utcnow()
    readings = [
        {'glucose_mg_dl': 150.0, 'timestamp': now, 'epoch_millis': int(now.timestamp() * 1000)},
        {'glucose_mg_dl': 220.0, 'timestamp': now + timedelta(hours=1), 'epoch_millis': int((now + timedelta(hours=1)).timestamp() * 1000)},
        {'glucose_mg_dl': 95.0, 'timestamp': now + timedelta(hours=2), 'epoch_millis': int((now + timedelta(hours=2)).timestamp() * 1000)},
    ]

    classifications = processor._classify_readings(readings)
    patterns = processor._identify_patterns(readings, classifications)

    assert len(patterns['hyperglycemic_events']) == 2
    assert any(e['severity'] == 'hyperglycemia' for e in patterns['hyperglycemic_events'])
    assert any(e['severity'] == 'severe_hyperglycemia' for e in patterns['hyperglycemic_events'])


@pytest.mark.asyncio
async def test_pattern_identification_fasting(processor):
    """Test identification of fasting readings (6-10 AM)."""
    # Create reading at 8 AM
    fasting_time = datetime(2025, 11, 18, 8, 0, 0)
    readings = [
        {'glucose_mg_dl': 90.0, 'timestamp': fasting_time, 'epoch_millis': int(fasting_time.timestamp() * 1000)},
        {'glucose_mg_dl': 110.0, 'timestamp': datetime(2025, 11, 18, 14, 0, 0), 'epoch_millis': int(datetime(2025, 11, 18, 14, 0, 0).timestamp() * 1000)},
    ]

    classifications = processor._classify_readings(readings)
    patterns = processor._identify_patterns(readings, classifications)

    assert len(patterns['fasting_readings']) == 1
    assert patterns['fasting_readings'][0]['glucose'] == 90.0


@pytest.mark.asyncio
async def test_pattern_identification_post_meal(processor):
    """Test identification of post-meal readings."""
    now = datetime.utcnow()
    readings = [
        {'glucose_mg_dl': 140.0, 'timestamp': now, 'relation_to_meal': 'AFTER_MEAL', 'epoch_millis': int(now.timestamp() * 1000)},
        {'glucose_mg_dl': 90.0, 'timestamp': now + timedelta(hours=1), 'relation_to_meal': None, 'epoch_millis': int((now + timedelta(hours=1)).timestamp() * 1000)},
    ]

    classifications = processor._classify_readings(readings)
    patterns = processor._identify_patterns(readings, classifications)

    assert len(patterns['post_meal_readings']) == 1
    assert patterns['post_meal_readings'][0]['glucose'] == 140.0


@pytest.mark.asyncio
async def test_pattern_identification_overnight(processor):
    """Test identification of overnight readings (10 PM - 6 AM)."""
    # Create overnight readings
    overnight_time1 = datetime(2025, 11, 18, 23, 0, 0)  # 11 PM
    overnight_time2 = datetime(2025, 11, 19, 2, 0, 0)   # 2 AM
    day_time = datetime(2025, 11, 18, 14, 0, 0)         # 2 PM

    readings = [
        {'glucose_mg_dl': 100.0, 'timestamp': overnight_time1, 'epoch_millis': int(overnight_time1.timestamp() * 1000)},
        {'glucose_mg_dl': 95.0, 'timestamp': overnight_time2, 'epoch_millis': int(overnight_time2.timestamp() * 1000)},
        {'glucose_mg_dl': 110.0, 'timestamp': day_time, 'epoch_millis': int(day_time.timestamp() * 1000)},
    ]

    classifications = processor._classify_readings(readings)
    patterns = processor._identify_patterns(readings, classifications)

    assert len(patterns['overnight_readings']) == 2


@pytest.mark.asyncio
async def test_analyze_trends_improving(processor):
    """Test trend analysis for improving glucose."""
    now = datetime.utcnow()
    # Create 10 readings: first 5 high, last 5 lower
    readings = []
    for i in range(5):
        readings.append({
            'glucose_mg_dl': 150.0,
            'timestamp': now + timedelta(hours=i),
            'epoch_millis': int((now + timedelta(hours=i)).timestamp() * 1000)
        })
    for i in range(5, 10):
        readings.append({
            'glucose_mg_dl': 100.0,
            'timestamp': now + timedelta(hours=i),
            'epoch_millis': int((now + timedelta(hours=i)).timestamp() * 1000)
        })

    trends = processor._analyze_trends(readings)

    assert trends is not None
    assert trends['trend'] == 'improving'
    assert trends['change_percent'] < -5


@pytest.mark.asyncio
async def test_analyze_trends_worsening(processor):
    """Test trend analysis for worsening glucose."""
    now = datetime.utcnow()
    # Create 10 readings: first 5 low, last 5 high
    readings = []
    for i in range(5):
        readings.append({
            'glucose_mg_dl': 100.0,
            'timestamp': now + timedelta(hours=i),
            'epoch_millis': int((now + timedelta(hours=i)).timestamp() * 1000)
        })
    for i in range(5, 10):
        readings.append({
            'glucose_mg_dl': 150.0,
            'timestamp': now + timedelta(hours=i),
            'epoch_millis': int((now + timedelta(hours=i)).timestamp() * 1000)
        })

    trends = processor._analyze_trends(readings)

    assert trends is not None
    assert trends['trend'] == 'worsening'
    assert trends['change_percent'] > 5


@pytest.mark.asyncio
async def test_analyze_trends_stable(processor):
    """Test trend analysis for stable glucose."""
    now = datetime.utcnow()
    # Create 10 readings with similar values
    readings = []
    for i in range(10):
        readings.append({
            'glucose_mg_dl': 120.0,
            'timestamp': now + timedelta(hours=i),
            'epoch_millis': int((now + timedelta(hours=i)).timestamp() * 1000)
        })

    trends = processor._analyze_trends(readings)

    assert trends is not None
    assert trends['trend'] == 'stable'
    assert abs(trends['change_percent']) < 5


@pytest.mark.asyncio
async def test_narrative_generation_normal_control(processor):
    """Test narrative for well-controlled glucose."""
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
    assert 'time in target range' in narrative.lower() or 'time in range' in narrative.lower()
    assert 'mg/dL' in narrative


@pytest.mark.asyncio
async def test_narrative_generation_with_hypoglycemia(processor):
    """Test narrative includes hypoglycemia warnings."""
    now = datetime.utcnow()
    readings = [
        {'glucose_mg_dl': 45.0, 'timestamp': now, 'epoch_millis': int(now.timestamp() * 1000), 'relation_to_meal': None},  # Severe hypo
        {'glucose_mg_dl': 65.0, 'timestamp': now + timedelta(hours=1), 'epoch_millis': int((now + timedelta(hours=1)).timestamp() * 1000), 'relation_to_meal': None},  # Mild hypo
        {'glucose_mg_dl': 100.0, 'timestamp': now + timedelta(hours=2), 'epoch_millis': int((now + timedelta(hours=2)).timestamp() * 1000), 'relation_to_meal': None},
    ]

    classifications = processor._classify_readings(readings)
    patterns = processor._identify_patterns(readings, classifications)
    metrics = processor._calculate_variability_metrics(readings)

    narrative = processor._generate_narrative(
        readings, classifications, patterns, metrics
    )

    assert 'alert' in narrative.lower() or 'severe' in narrative.lower()
    assert 'hypoglycemic' in narrative.lower()


@pytest.mark.asyncio
async def test_clinical_insights_extraction(processor):
    """Test extraction of structured clinical insights."""
    now = datetime.utcnow()
    readings = []
    # Mix of normal, hypo, and hyper readings
    for i in range(10):
        glucose = 100.0 if i % 3 == 0 else (65.0 if i % 3 == 1 else 185.0)
        readings.append({
            'glucose_mg_dl': glucose,
            'timestamp': now + timedelta(hours=i),
            'epoch_millis': int((now + timedelta(hours=i)).timestamp() * 1000),
        })

    classifications = processor._classify_readings(readings)
    patterns = processor._identify_patterns(readings, classifications)
    metrics = processor._calculate_variability_metrics(readings)

    insights = processor._extract_clinical_insights(
        classifications, patterns, metrics
    )

    assert insights['record_type'] == 'BloodGlucoseRecord'
    assert insights['total_readings'] == 10
    assert 'critical_events' in insights
    assert 'warning_events' in insights
    assert 'normal_events' in insights
    assert 'variability_metrics' in insights
    assert 'control_status' in insights
    assert insights['control_status'] in ['excellent', 'good', 'fair', 'poor']


@pytest.mark.asyncio
async def test_clinical_insights_control_status_excellent(processor):
    """Test control status is 'excellent' for well-controlled glucose."""
    now = datetime.utcnow()
    # Create readings with low CV and high TIR
    readings = []
    for i in range(20):
        readings.append({
            'glucose_mg_dl': 100.0 + (i % 10),  # Values 100-110
            'timestamp': now + timedelta(hours=i),
        })

    classifications = processor._classify_readings(readings)
    patterns = processor._identify_patterns(readings, classifications)
    metrics = processor._calculate_variability_metrics(readings)

    insights = processor._extract_clinical_insights(
        classifications, patterns, metrics
    )

    assert insights['control_status'] == 'excellent'


@pytest.mark.asyncio
async def test_end_to_end_processing(processor):
    """Test complete processing pipeline."""
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
    assert result.records_processed == len(records)
    assert result.quality_score == 0.95


@pytest.mark.asyncio
async def test_processing_with_no_valid_readings(processor):
    """Test processing handles files with no valid readings."""
    # All records are malformed
    records = [
        {'invalid': 'data'},
        {'also': 'invalid'},
    ]

    message_data = {
        'bucket': 'health-data',
        'key': 'raw/BloodGlucoseRecord/2025/11/invalid.avro',
        'record_type': 'BloodGlucoseRecord',
    }

    validation_result = ValidationResult(
        is_valid=True,
        errors=[],
        warnings=[],
        quality_score=0.5,
        metadata={}
    )

    result = await processor.process_with_clinical_insights(
        records, message_data, validation_result
    )

    assert result.success is False
    assert 'No valid glucose readings found' in result.error_message


@pytest.mark.asyncio
async def test_processing_handles_exceptions(processor):
    """Test processing handles unexpected exceptions gracefully."""
    # Pass None to trigger exception
    records = None

    message_data = {}
    validation_result = ValidationResult(is_valid=True)

    result = await processor.process_with_clinical_insights(
        records, message_data, validation_result
    )

    assert result.success is False
    assert result.error_message is not None
    assert 'failed' in result.error_message.lower()


# Helper functions

def create_sample_glucose_avro_records() -> list[dict]:
    """Helper to create realistic glucose records."""
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
            'level': {'inMilligramsPerDeciliter': float(glucose)},
            'time': {'epochMillis': int(timestamp.timestamp() * 1000)},
            'metadata': {},
            'specimenSource': 'FINGERSTICK'
        })

    return records
