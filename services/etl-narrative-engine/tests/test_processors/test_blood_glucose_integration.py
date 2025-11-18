"""
Integration tests for Blood Glucose Processor with real Avro files.

These tests use actual sample Avro files to verify the processor works
correctly with real-world data from Android Health Connect.
"""

from pathlib import Path

import pytest
from fastavro import reader

from src.processors.blood_glucose_processor import BloodGlucoseProcessor
from src.validation.data_quality import ValidationResult


@pytest.fixture
def sample_files_dir():
    """Get path to sample Avro files directory."""
    # From services/etl-narrative-engine/tests/ to project root
    project_root = Path(__file__).parent.parent.parent.parent.parent
    return project_root / "docs" / "sample-avro-files"


@pytest.fixture
def blood_glucose_files(sample_files_dir):
    """Get list of BloodGlucoseRecord sample files."""
    return list(sample_files_dir.glob("BloodGlucoseRecord_*.avro"))


@pytest.fixture
async def processor():
    """Create and initialize glucose processor."""
    proc = BloodGlucoseProcessor()
    await proc.initialize()
    return proc


@pytest.mark.integration
@pytest.mark.asyncio
async def test_process_real_glucose_file(processor, blood_glucose_files):
    """Test processing with actual sample Avro file."""
    # Use first available sample file
    if not blood_glucose_files:
        pytest.skip("No BloodGlucoseRecord sample files found")

    sample_file = blood_glucose_files[0]

    # Load real sample file
    with open(sample_file, 'rb') as f:
        records = list(reader(f))

    message_data = {
        'bucket': 'health-data',
        'key': f'raw/BloodGlucoseRecord/2025/11/{sample_file.name}',
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
    assert result.success is True, f"Processing failed: {result.error_message}"
    assert result.narrative is not None
    assert len(result.narrative) > 0
    assert result.records_processed > 0

    # Verify clinical insights structure
    insights = result.clinical_insights
    assert 'total_readings' in insights
    assert 'variability_metrics' in insights
    assert 'control_status' in insights
    assert insights['record_type'] == 'BloodGlucoseRecord'

    # Print narrative for manual review
    print("\n" + "=" * 80)
    print(f"FILE: {sample_file.name}")
    print("=" * 80)
    print("GENERATED NARRATIVE:")
    print("=" * 80)
    print(result.narrative)
    print("=" * 80)
    print("\nCLINICAL INSIGHTS:")
    print("=" * 80)
    print(f"Total Readings: {insights['total_readings']}")
    print(f"Control Status: {insights['control_status']}")
    print(f"Critical Events: {insights['critical_events']}")
    print(f"Warning Events: {insights['warning_events']}")
    print(f"Normal Events: {insights['normal_events']}")
    print(f"Hypoglycemic Events: {insights['hypoglycemic_events_count']}")
    print(f"Hyperglycemic Events: {insights['hyperglycemic_events_count']}")
    if 'variability_metrics' in insights and isinstance(insights['variability_metrics'], dict):
        metrics = insights['variability_metrics']
        if 'mean_glucose' in metrics:
            print(f"Mean Glucose: {metrics['mean_glucose']} mg/dL")
            print(f"CV: {metrics.get('coefficient_of_variation', 'N/A')}%")
            print(f"Time in Range: {metrics.get('time_in_range_percent', 'N/A')}%")
    print("=" * 80)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_process_multiple_glucose_files(processor, blood_glucose_files):
    """Test processing multiple sample files."""
    if len(blood_glucose_files) < 2:
        pytest.skip("Need at least 2 BloodGlucoseRecord sample files")

    results = []

    for sample_file in blood_glucose_files[:3]:  # Test first 3 files
        with open(sample_file, 'rb') as f:
            records = list(reader(f))

        message_data = {
            'bucket': 'health-data',
            'key': f'raw/BloodGlucoseRecord/2025/11/{sample_file.name}',
            'record_type': 'BloodGlucoseRecord',
            'user_id': 'integration_test',
            'correlation_id': f'test-{sample_file.stem}'
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

        results.append((sample_file.name, result))

    # Verify all files processed successfully
    for filename, result in results:
        assert result.success is True, f"Failed to process {filename}: {result.error_message}"
        assert result.narrative is not None
        assert result.clinical_insights is not None

    print("\n" + "=" * 80)
    print(f"Successfully processed {len(results)} BloodGlucoseRecord files")
    print("=" * 80)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_verify_glucose_extraction_from_real_file(processor, blood_glucose_files):
    """Verify glucose values are correctly extracted from real files."""
    if not blood_glucose_files:
        pytest.skip("No BloodGlucoseRecord sample files found")

    sample_file = blood_glucose_files[0]

    with open(sample_file, 'rb') as f:
        records = list(reader(f))

    # Extract readings
    readings = processor._extract_glucose_readings(records)

    # Verify readings were extracted
    assert len(readings) > 0, "No readings extracted from sample file"

    # Verify reading structure
    for reading in readings:
        assert 'glucose_mg_dl' in reading
        assert 'timestamp' in reading
        assert reading['glucose_mg_dl'] > 0, "Glucose value should be positive"
        assert reading['glucose_mg_dl'] < 1000, "Glucose value seems unrealistic"

    print(f"\nExtracted {len(readings)} readings from {sample_file.name}")
    print(f"Sample reading: {readings[0]}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_verify_classifications_from_real_file(processor, blood_glucose_files):
    """Verify glucose classifications from real file data."""
    if not blood_glucose_files:
        pytest.skip("No BloodGlucoseRecord sample files found")

    sample_file = blood_glucose_files[0]

    with open(sample_file, 'rb') as f:
        records = list(reader(f))

    readings = processor._extract_glucose_readings(records)
    classifications = processor._classify_readings(readings)

    # Verify classifications
    assert len(classifications) == len(readings)

    # Count by category
    categories = {}
    for classification in classifications:
        category = classification['category']
        categories[category] = categories.get(category, 0) + 1

    print(f"\nClassifications from {sample_file.name}:")
    for category, count in sorted(categories.items()):
        print(f"  {category}: {count}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_verify_metrics_from_real_file(processor, blood_glucose_files):
    """Verify variability metrics calculation from real file data."""
    if not blood_glucose_files:
        pytest.skip("No BloodGlucoseRecord sample files found")

    sample_file = blood_glucose_files[0]

    with open(sample_file, 'rb') as f:
        records = list(reader(f))

    readings = processor._extract_glucose_readings(records)

    if len(readings) < 2:
        pytest.skip("Need at least 2 readings to calculate metrics")

    metrics = processor._calculate_variability_metrics(readings)

    # Verify metrics structure
    assert 'mean_glucose' in metrics
    assert 'coefficient_of_variation' in metrics
    assert 'time_in_range_percent' in metrics

    # Verify metrics are reasonable
    assert 0 < metrics['mean_glucose'] < 500, "Mean glucose should be in reasonable range"
    assert 0 <= metrics['coefficient_of_variation'] <= 200, "CV should be percentage"
    assert 0 <= metrics['time_in_range_percent'] <= 100, "TIR should be percentage"

    print(f"\nMetrics from {sample_file.name}:")
    print(f"  Mean Glucose: {metrics['mean_glucose']} mg/dL")
    print(f"  CV: {metrics['coefficient_of_variation']}%")
    print(f"  Time in Range: {metrics['time_in_range_percent']}%")
    print(f"  Time Below Range: {metrics['time_below_range_percent']}%")
    print(f"  Time Above Range: {metrics['time_above_range_percent']}%")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_narrative_quality_from_real_file(processor, blood_glucose_files):
    """Verify narrative quality from real file data."""
    if not blood_glucose_files:
        pytest.skip("No BloodGlucoseRecord sample files found")

    sample_file = blood_glucose_files[0]

    with open(sample_file, 'rb') as f:
        records = list(reader(f))

    message_data = {
        'bucket': 'health-data',
        'key': f'raw/BloodGlucoseRecord/2025/11/{sample_file.name}',
        'record_type': 'BloodGlucoseRecord',
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

    assert result.success is True
    narrative = result.narrative

    # Verify narrative content quality
    assert len(narrative) > 100, "Narrative should be substantial"
    assert 'mg/dL' in narrative, "Should include units"
    assert any(word in narrative.lower() for word in ['glucose', 'blood']), "Should mention glucose"

    # Verify narrative includes key information
    insights = result.clinical_insights
    if insights['hypoglycemic_events_count'] > 0:
        assert 'hypoglycemic' in narrative.lower() or 'low' in narrative.lower()
    if insights['hyperglycemic_events_count'] > 0:
        assert 'hyperglycemic' in narrative.lower() or 'elevated' in narrative.lower() or 'high' in narrative.lower()

    print(f"\nNarrative Quality Check for {sample_file.name}:")
    print(f"  Length: {len(narrative)} characters")
    print(f"  Contains units: {'mg/dL' in narrative}")
    print(f"  Contains glucose mention: {any(word in narrative.lower() for word in ['glucose', 'blood'])}")
