"""
Tests for processor factory and base processor interface.

Tests Module 1 processor routing and mock processor functionality.
"""

import pytest
from src.processors.processor_factory import ProcessorFactory, MockProcessor
from src.processors.base_processor import ProcessingResult


@pytest.mark.unit
@pytest.mark.asyncio
async def test_processor_factory_initialization():
    """Verify processor factory initializes all processors"""
    factory = ProcessorFactory()
    await factory.initialize()

    # Should have processors for all supported types
    assert len(factory._processors) == 6

    # Check each supported type
    for record_type in factory.SUPPORTED_TYPES:
        processor = factory.get_processor(record_type)
        assert processor is not None
        assert isinstance(processor, MockProcessor)

    await factory.cleanup()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_processor_factory_get_processor():
    """Verify correct processor is returned for record type"""
    factory = ProcessorFactory()
    await factory.initialize()

    # Test blood glucose processor
    processor = factory.get_processor("BloodGlucoseRecord")
    assert processor is not None
    assert processor.record_type == "BloodGlucoseRecord"

    # Test heart rate processor
    processor = factory.get_processor("HeartRateRecord")
    assert processor is not None
    assert processor.record_type == "HeartRateRecord"

    await factory.cleanup()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_processor_factory_unsupported_type():
    """Verify error for unsupported record type"""
    factory = ProcessorFactory()
    await factory.initialize()

    # Should raise ValueError for unsupported type
    with pytest.raises(ValueError, match="Unsupported record type"):
        factory.get_processor("UnsupportedRecordType")

    await factory.cleanup()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mock_processor_initialization():
    """Verify mock processor initializes correctly"""
    processor = MockProcessor("BloodGlucoseRecord")
    await processor.initialize()

    assert processor.record_type == "BloodGlucoseRecord"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mock_processor_returns_success(sample_avro_records, sample_message_data):
    """Verify mock processor returns success result"""
    processor = MockProcessor("BloodGlucoseRecord")
    await processor.initialize()

    # Process records
    result = await processor.process_with_clinical_insights(
        records=sample_avro_records,
        message_data=sample_message_data,
        validation_result=None
    )

    # Verify result
    assert isinstance(result, ProcessingResult)
    assert result.success is True
    assert result.narrative is not None
    assert "BloodGlucoseRecord" in result.narrative
    assert result.error_message is None
    assert result.records_processed == len(sample_avro_records)
    assert result.quality_score > 0.0

    # Verify clinical insights
    assert result.clinical_insights is not None
    assert result.clinical_insights["mock"] is True
    assert result.clinical_insights["record_type"] == "BloodGlucoseRecord"
    assert result.clinical_insights["record_count"] == len(sample_avro_records)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mock_processor_cleanup():
    """Verify mock processor cleanup works"""
    processor = MockProcessor("BloodGlucoseRecord")
    await processor.initialize()

    # Should not raise error
    await processor.cleanup()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_processor_factory_cleanup_all():
    """Verify factory cleanup calls cleanup on all processors"""
    factory = ProcessorFactory()
    await factory.initialize()

    # Should not raise error
    await factory.cleanup()
