"""
Processor factory for routing messages to appropriate clinical processors.

This factory selects the correct processor based on record_type from the message.
All Module 3 processors are now real implementations (no more mocks).
"""

import structlog

from .active_calories_processor import ActiveCaloriesProcessor
from .base_processor import BaseClinicalProcessor
from .blood_glucose_processor import BloodGlucoseProcessor
from .heart_rate_processor import HeartRateProcessor
from .hrv_rmssd_processor import HRVRmssdProcessor
from .sleep_processor import SleepProcessor
from .steps_processor import StepsProcessor

logger = structlog.get_logger()


class ProcessorFactory:
    """
    Factory for creating clinical processors based on record type.

    Usage:
        factory = ProcessorFactory()
        await factory.initialize()
        processor = factory.get_processor("BloodGlucoseRecord")
        result = await processor.process_with_clinical_insights(...)
    """

    # Supported record types (from health-api-service)
    SUPPORTED_TYPES = [
        "BloodGlucoseRecord",
        "HeartRateRecord",
        "SleepSessionRecord",
        "StepsRecord",
        "ActiveCaloriesBurnedRecord",
        "HeartRateVariabilityRmssdRecord",
    ]

    def __init__(self):
        """Initialize the factory"""
        self.logger = structlog.get_logger()
        self._processors: dict[str, BaseClinicalProcessor] = {}

    async def initialize(self) -> None:
        """
        Initialize all processors.

        Module 3a/3b/3c processors:
        - BloodGlucoseRecord -> BloodGlucoseProcessor
        - HeartRateRecord -> HeartRateProcessor
        - SleepSessionRecord -> SleepProcessor

        Module 3d processors:
        - StepsRecord -> StepsProcessor
        - ActiveCaloriesBurnedRecord -> ActiveCaloriesProcessor
        - HeartRateVariabilityRmssdRecord -> HRVRmssdProcessor
        """
        self.logger.info("initializing_processor_factory")

        # Create all real processors
        self._processors["BloodGlucoseRecord"] = BloodGlucoseProcessor()
        self._processors["HeartRateRecord"] = HeartRateProcessor()
        self._processors["SleepSessionRecord"] = SleepProcessor()
        self._processors["StepsRecord"] = StepsProcessor()
        self._processors["ActiveCaloriesBurnedRecord"] = ActiveCaloriesProcessor()
        self._processors["HeartRateVariabilityRmssdRecord"] = HRVRmssdProcessor()

        # Initialize all processors
        for processor in self._processors.values():
            await processor.initialize()

        self.logger.info(
            "processor_factory_initialized",
            processor_count=len(self._processors),
            processors=list(self._processors.keys()),
        )

    def get_processor(self, record_type: str) -> BaseClinicalProcessor:
        """
        Get processor for a specific record type.

        Args:
            record_type: Health record type (e.g., "BloodGlucoseRecord")

        Returns:
            Processor instance

        Raises:
            ValueError: If record_type is not supported
        """
        if record_type not in self.SUPPORTED_TYPES:
            raise ValueError(
                f"Unsupported record type: {record_type}. "
                f"Supported types: {self.SUPPORTED_TYPES}"
            )

        processor = self._processors.get(record_type)
        if not processor:
            # This should never happen if initialize() was called
            self.logger.error("processor_not_initialized", record_type=record_type)
            raise RuntimeError(
                f"Processor for {record_type} not initialized. "
                "Call initialize() first."
            )
        return processor

    async def cleanup(self) -> None:
        """Cleanup all processors"""
        self.logger.info("cleaning_up_processors")
        for processor in self._processors.values():
            await processor.cleanup()
