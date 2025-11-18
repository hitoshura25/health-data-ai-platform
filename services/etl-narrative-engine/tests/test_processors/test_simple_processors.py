"""
Tests for simple health data processors (Module 3d).

Tests for StepsProcessor, ActiveCaloriesProcessor, and HRVRmssdProcessor.
"""


import pytest

from src.processors.active_calories_processor import ActiveCaloriesProcessor
from src.processors.base_processor import ProcessingResult
from src.processors.hrv_rmssd_processor import HRVRmssdProcessor
from src.processors.steps_processor import StepsProcessor

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_steps_records():
    """Sample steps records for testing"""
    return [
        {
            'count': 5000,
            'startTime': {'epochMillis': 1704067200000},  # 2024-01-01 00:00:00
            'endTime': {'epochMillis': 1704153600000},    # 2024-01-02 00:00:00
        },
        {
            'count': 8500,
            'startTime': {'epochMillis': 1704153600000},  # 2024-01-02 00:00:00
            'endTime': {'epochMillis': 1704240000000},    # 2024-01-03 00:00:00
        },
        {
            'count': 12000,
            'startTime': {'epochMillis': 1704240000000},  # 2024-01-03 00:00:00
            'endTime': {'epochMillis': 1704326400000},    # 2024-01-04 00:00:00
        },
    ]


@pytest.fixture
def sample_calorie_records():
    """Sample active calories records for testing"""
    return [
        {
            'energy': {'inCalories': 450},
            'startTime': {'epochMillis': 1704067200000},
            'endTime': {'epochMillis': 1704153600000},
        },
        {
            'energy': {'inKilocalories': 550},
            'startTime': {'epochMillis': 1704153600000},
            'endTime': {'epochMillis': 1704240000000},
        },
        {
            'energy': {'inCalories': 350},
            'startTime': {'epochMillis': 1704240000000},
            'endTime': {'epochMillis': 1704326400000},
        },
    ]


@pytest.fixture
def sample_hrv_records():
    """Sample HRV RMSSD records for testing"""
    return [
        {
            'heartRateVariabilityRmssd': {'inMilliseconds': 45.5},
            'time': {'epochMillis': 1704067200000},
        },
        {
            'heartRateVariabilityRmssd': {'inMilliseconds': 52.3},
            'time': {'epochMillis': 1704153600000},
        },
        {
            'heartRateVariabilityRmssd': {'inMilliseconds': 48.7},
            'time': {'epochMillis': 1704240000000},
        },
    ]


@pytest.fixture
def sample_hrv_records_for_trends():
    """Sample HRV records with enough data for trend analysis"""
    base_timestamp = 1704067200000
    records = []

    # First half: lower HRV values
    for i in range(7):
        records.append({
            'heartRateVariabilityRmssd': {'inMilliseconds': 40 + i},
            'time': {'epochMillis': base_timestamp + (i * 86400000)},
        })

    # Second half: higher HRV values (showing improvement)
    for i in range(7):
        records.append({
            'heartRateVariabilityRmssd': {'inMilliseconds': 55 + i},
            'time': {'epochMillis': base_timestamp + ((i + 7) * 86400000)},
        })

    return records


# ============================================================================
# StepsProcessor Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_steps_processor_initialization():
    """Verify steps processor initializes correctly"""
    processor = StepsProcessor()
    await processor.initialize()

    assert processor.daily_target == 10000
    assert processor.weekly_target == 70000


@pytest.mark.unit
@pytest.mark.asyncio
async def test_steps_processor_success(sample_steps_records):
    """Verify steps processor processes records successfully"""
    processor = StepsProcessor()
    await processor.initialize()

    result = await processor.process_with_clinical_insights(
        records=sample_steps_records,
        message_data={},
        validation_result=None
    )

    assert isinstance(result, ProcessingResult)
    assert result.success is True
    assert result.narrative is not None
    assert 'step' in result.narrative.lower()
    assert result.error_message is None
    assert result.records_processed == len(sample_steps_records)

    # Verify clinical insights
    assert result.clinical_insights is not None
    assert result.clinical_insights['record_type'] == 'StepsRecord'
    assert result.clinical_insights['total_records'] == 3
    assert 'metrics' in result.clinical_insights
    assert 'daily_steps' in result.clinical_insights


@pytest.mark.unit
@pytest.mark.asyncio
async def test_steps_processor_metrics(sample_steps_records):
    """Verify steps processor calculates correct metrics"""
    processor = StepsProcessor()
    await processor.initialize()

    result = await processor.process_with_clinical_insights(
        records=sample_steps_records,
        message_data={},
        validation_result=None
    )

    metrics = result.clinical_insights['metrics']
    assert metrics['total_days'] == 3
    assert metrics['avg_daily_steps'] == 8500  # (5000 + 8500 + 12000) / 3
    assert metrics['max_daily_steps'] == 12000
    assert metrics['min_daily_steps'] == 5000
    assert metrics['days_meeting_target'] == 1  # Only 12000 meets 10k target
    assert metrics['total_steps'] == 25500


@pytest.mark.unit
@pytest.mark.asyncio
async def test_steps_processor_empty_records():
    """Verify steps processor handles empty records"""
    processor = StepsProcessor()
    await processor.initialize()

    result = await processor.process_with_clinical_insights(
        records=[],
        message_data={},
        validation_result=None
    )

    assert result.success is False
    assert result.error_message is not None
    assert 'No valid step records' in result.error_message


@pytest.mark.unit
@pytest.mark.asyncio
async def test_steps_processor_narrative_excellent():
    """Verify narrative for excellent activity level"""
    processor = StepsProcessor()
    await processor.initialize()

    # Create records with high step counts
    high_steps_records = [
        {
            'count': 12000,
            'startTime': {'epochMillis': 1704067200000 + i * 86400000},
            'endTime': {'epochMillis': 1704153600000 + i * 86400000},
        }
        for i in range(7)
    ]

    result = await processor.process_with_clinical_insights(
        records=high_steps_records,
        message_data={},
        validation_result=None
    )

    assert 'excellent' in result.narrative.lower()
    assert 'WHO recommendation' in result.narrative


# ============================================================================
# ActiveCaloriesProcessor Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_active_calories_processor_initialization():
    """Verify active calories processor initializes correctly"""
    processor = ActiveCaloriesProcessor()
    await processor.initialize()

    assert processor.daily_target == 500
    assert processor.weekly_target == 3500


@pytest.mark.unit
@pytest.mark.asyncio
async def test_active_calories_processor_success(sample_calorie_records):
    """Verify active calories processor processes records successfully"""
    processor = ActiveCaloriesProcessor()
    await processor.initialize()

    result = await processor.process_with_clinical_insights(
        records=sample_calorie_records,
        message_data={},
        validation_result=None
    )

    assert isinstance(result, ProcessingResult)
    assert result.success is True
    assert result.narrative is not None
    assert 'calorie' in result.narrative.lower()
    assert result.error_message is None
    assert result.records_processed == len(sample_calorie_records)

    # Verify clinical insights
    assert result.clinical_insights is not None
    assert result.clinical_insights['record_type'] == 'ActiveCaloriesBurnedRecord'
    assert result.clinical_insights['total_records'] == 3
    assert 'metrics' in result.clinical_insights
    assert 'daily_calories' in result.clinical_insights


@pytest.mark.unit
@pytest.mark.asyncio
async def test_active_calories_processor_metrics(sample_calorie_records):
    """Verify active calories processor calculates correct metrics"""
    processor = ActiveCaloriesProcessor()
    await processor.initialize()

    result = await processor.process_with_clinical_insights(
        records=sample_calorie_records,
        message_data={},
        validation_result=None
    )

    metrics = result.clinical_insights['metrics']
    assert metrics['total_days'] == 3
    assert metrics['avg_daily_calories'] == 450  # (450 + 550 + 350) / 3
    assert metrics['max_daily_calories'] == 550
    assert metrics['min_daily_calories'] == 350
    assert metrics['days_meeting_target'] == 1  # Only 550 meets 500 target
    assert metrics['total_calories'] == 1350


@pytest.mark.unit
@pytest.mark.asyncio
async def test_active_calories_processor_empty_records():
    """Verify active calories processor handles empty records"""
    processor = ActiveCaloriesProcessor()
    await processor.initialize()

    result = await processor.process_with_clinical_insights(
        records=[],
        message_data={},
        validation_result=None
    )

    assert result.success is False
    assert result.error_message is not None
    assert 'No valid calorie records' in result.error_message


@pytest.mark.unit
@pytest.mark.asyncio
async def test_active_calories_processor_narrative_high():
    """Verify narrative for very high activity level"""
    processor = ActiveCaloriesProcessor()
    await processor.initialize()

    # Create records with high calorie burn
    high_calorie_records = [
        {
            'energy': {'inCalories': 700},
            'startTime': {'epochMillis': 1704067200000 + i * 86400000},
            'endTime': {'epochMillis': 1704153600000 + i * 86400000},
        }
        for i in range(7)
    ]

    result = await processor.process_with_clinical_insights(
        records=high_calorie_records,
        message_data={},
        validation_result=None
    )

    assert 'very high' in result.narrative.lower()
    assert 'intensive' in result.narrative.lower()


# ============================================================================
# HRVRmssdProcessor Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hrv_processor_initialization():
    """Verify HRV processor initializes correctly"""
    processor = HRVRmssdProcessor()
    await processor.initialize()

    assert processor.optimal_hrv_threshold == 60


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hrv_processor_success(sample_hrv_records):
    """Verify HRV processor processes records successfully"""
    processor = HRVRmssdProcessor()
    await processor.initialize()

    result = await processor.process_with_clinical_insights(
        records=sample_hrv_records,
        message_data={},
        validation_result=None
    )

    assert isinstance(result, ProcessingResult)
    assert result.success is True
    assert result.narrative is not None
    assert ('hrv' in result.narrative.lower() or 'variability' in result.narrative.lower())
    assert result.error_message is None
    assert result.records_processed == len(sample_hrv_records)

    # Verify clinical insights
    assert result.clinical_insights is not None
    assert result.clinical_insights['record_type'] == 'HeartRateVariabilityRmssdRecord'
    assert result.clinical_insights['total_readings'] == 3
    assert 'metrics' in result.clinical_insights
    assert 'trends' in result.clinical_insights


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hrv_processor_metrics(sample_hrv_records):
    """Verify HRV processor calculates correct metrics"""
    processor = HRVRmssdProcessor()
    await processor.initialize()

    result = await processor.process_with_clinical_insights(
        records=sample_hrv_records,
        message_data={},
        validation_result=None
    )

    metrics = result.clinical_insights['metrics']
    assert metrics['total_readings'] == 3
    assert 48.0 <= metrics['avg_hrv_rmssd'] <= 49.0  # ~48.8
    assert metrics['min_hrv'] == 45.5
    assert metrics['max_hrv'] == 52.3
    assert metrics['hrv_category'] == 'average'
    assert metrics['recovery_status'] == 'normal'


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hrv_processor_empty_records():
    """Verify HRV processor handles empty records"""
    processor = HRVRmssdProcessor()
    await processor.initialize()

    result = await processor.process_with_clinical_insights(
        records=[],
        message_data={},
        validation_result=None
    )

    assert result.success is False
    assert result.error_message is not None
    assert 'No valid HRV readings' in result.error_message


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hrv_processor_trend_analysis(sample_hrv_records_for_trends):
    """Verify HRV processor analyzes trends correctly"""
    processor = HRVRmssdProcessor()
    await processor.initialize()

    result = await processor.process_with_clinical_insights(
        records=sample_hrv_records_for_trends,
        message_data={},
        validation_result=None
    )

    trends = result.clinical_insights['trends']
    assert 'insufficient_data' not in trends
    assert trends['trend'] == 'improving'
    assert trends['change_percent'] > 10
    assert 'improving' in trends['description'].lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hrv_processor_excellent_recovery():
    """Verify narrative for excellent HRV"""
    processor = HRVRmssdProcessor()
    await processor.initialize()

    # Create records with excellent HRV
    excellent_hrv_records = [
        {
            'heartRateVariabilityRmssd': {'inMilliseconds': 85},
            'time': {'epochMillis': 1704067200000 + i * 86400000},
        }
        for i in range(3)
    ]

    result = await processor.process_with_clinical_insights(
        records=excellent_hrv_records,
        message_data={},
        validation_result=None
    )

    assert 'excellent' in result.narrative.lower()
    assert 'cardiovascular fitness' in result.narrative.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hrv_processor_poor_recovery():
    """Verify narrative for low HRV"""
    processor = HRVRmssdProcessor()
    await processor.initialize()

    # Create records with low HRV
    low_hrv_records = [
        {
            'heartRateVariabilityRmssd': {'inMilliseconds': 15},
            'time': {'epochMillis': 1704067200000 + i * 86400000},
        }
        for i in range(3)
    ]

    result = await processor.process_with_clinical_insights(
        records=low_hrv_records,
        message_data={},
        validation_result=None
    )

    assert 'below optimal' in result.narrative.lower()
    assert ('stress' in result.narrative.lower() or 'recovery' in result.narrative.lower())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hrv_processor_insufficient_data_for_trends():
    """Verify HRV processor handles insufficient data for trends"""
    processor = HRVRmssdProcessor()
    await processor.initialize()

    # Only 3 records - not enough for trend analysis
    result = await processor.process_with_clinical_insights(
        records=[
            {
                'heartRateVariabilityRmssd': {'inMilliseconds': 50},
                'time': {'epochMillis': 1704067200000 + i * 86400000},
            }
            for i in range(3)
        ],
        message_data={},
        validation_result=None
    )

    trends = result.clinical_insights['trends']
    assert trends.get('insufficient_data') is True
