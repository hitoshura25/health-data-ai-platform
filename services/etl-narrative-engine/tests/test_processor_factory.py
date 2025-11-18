"""
Tests for processor factory and base processor interface.

Tests all Module 3 real processor integration.
"""

import pytest

from src.processors.active_calories_processor import ActiveCaloriesProcessor
from src.processors.base_processor import BaseClinicalProcessor
from src.processors.blood_glucose_processor import BloodGlucoseProcessor
from src.processors.heart_rate_processor import HeartRateProcessor
from src.processors.hrv_rmssd_processor import HRVRmssdProcessor
from src.processors.processor_factory import ProcessorFactory
from src.processors.sleep_processor import SleepProcessor
from src.processors.steps_processor import StepsProcessor


@pytest.mark.unit
@pytest.mark.asyncio
async def test_processor_factory_initialization():
    """Verify processor factory initializes all processors"""
    factory = ProcessorFactory()
    await factory.initialize()

    # Should have processors for all supported types
    assert len(factory._processors) == 6

    # Check each supported type has a processor
    for record_type in factory.SUPPORTED_TYPES:
        processor = factory.get_processor(record_type)
        assert processor is not None
        # All processors should inherit from BaseClinicalProcessor
        assert isinstance(processor, BaseClinicalProcessor)

    # Verify all real processors are initialized
    assert isinstance(factory.get_processor("BloodGlucoseRecord"), BloodGlucoseProcessor)
    assert isinstance(factory.get_processor("HeartRateRecord"), HeartRateProcessor)
    assert isinstance(factory.get_processor("SleepSessionRecord"), SleepProcessor)
    assert isinstance(factory.get_processor("StepsRecord"), StepsProcessor)
    assert isinstance(
        factory.get_processor("ActiveCaloriesBurnedRecord"), ActiveCaloriesProcessor
    )
    assert isinstance(
        factory.get_processor("HeartRateVariabilityRmssdRecord"), HRVRmssdProcessor
    )

    await factory.cleanup()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_processor_factory_get_processor():
    """Verify correct processor is returned for record type"""
    factory = ProcessorFactory()
    await factory.initialize()

    # Test Module 3a/3b/3c processors
    processor = factory.get_processor("BloodGlucoseRecord")
    assert processor is not None
    assert isinstance(processor, BloodGlucoseProcessor)

    processor = factory.get_processor("HeartRateRecord")
    assert processor is not None
    assert isinstance(processor, HeartRateProcessor)

    processor = factory.get_processor("SleepSessionRecord")
    assert processor is not None
    assert isinstance(processor, SleepProcessor)

    # Test Module 3d processors
    processor = factory.get_processor("StepsRecord")
    assert processor is not None
    assert isinstance(processor, StepsProcessor)

    processor = factory.get_processor("ActiveCaloriesBurnedRecord")
    assert processor is not None
    assert isinstance(processor, ActiveCaloriesProcessor)

    processor = factory.get_processor("HeartRateVariabilityRmssdRecord")
    assert processor is not None
    assert isinstance(processor, HRVRmssdProcessor)

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
async def test_processor_factory_cleanup_all():
    """Verify factory cleanup calls cleanup on all processors"""
    factory = ProcessorFactory()
    await factory.initialize()

    # Should not raise error
    await factory.cleanup()
