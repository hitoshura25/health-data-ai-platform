"""
Processor factory for routing messages to appropriate clinical processors.

This factory selects the correct processor based on record_type from the message.
For Module 1, this provides stub/mock processors. Real processors come from Module 3.
"""
import structlog

from .base_processor import BaseClinicalProcessor, ProcessingResult

logger = structlog.get_logger()

# Mock processor constants for Module 1 (placeholders for real clinical processing in Module 3)
MOCK_QUALITY_SCORE = 0.95  # Stub quality score until real clinical analysis in Module 3
MOCK_PROCESSING_TIME_SECONDS = 0.1  # Stub processing time for mock processor


class MockProcessor(BaseClinicalProcessor):
    """
    Mock processor for Module 1 testing.

    Returns a simple success result without actual clinical processing.
    Real processors will be implemented in Module 3.
    """

    def __init__(self, record_type: str):
        super().__init__()
        self.record_type = record_type

    async def initialize(self) -> None:
        """Initialize mock processor"""
        self.logger.info("mock_processor_initialized", record_type=self.record_type)

    async def process_with_clinical_insights(
        self,
        records,
        message_data,
        validation_result
    ) -> ProcessingResult:
        """Return mock processing result"""
        record_count = len(records)

        # Generate simple mock narrative
        narrative = (
            f"Mock processing of {record_count} {self.record_type} records. "
            f"This is a stub processor from Module 1. Real clinical processing "
            f"will be implemented in Module 3."
        )

        return ProcessingResult(
            success=True,
            narrative=narrative,
            error_message=None,
            processing_time_seconds=MOCK_PROCESSING_TIME_SECONDS,
            records_processed=record_count,
            quality_score=MOCK_QUALITY_SCORE,
            clinical_insights={
                "mock": True,
                "record_type": self.record_type,
                "record_count": record_count
            }
        )


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
        "HeartRateVariabilityRmssdRecord"
    ]

    def __init__(self):
        """Initialize the factory"""
        self.logger = structlog.get_logger()
        self._processors: dict[str, BaseClinicalProcessor] = {}

    async def initialize(self) -> None:
        """
        Initialize all processors.

        For Module 1, this creates mock processors for each type.
        Module 3 will replace with real clinical processors.
        """
        self.logger.info("initializing_processor_factory")

        for record_type in self.SUPPORTED_TYPES:
            processor = MockProcessor(record_type)
            await processor.initialize()
            self._processors[record_type] = processor

        self.logger.info(
            "processor_factory_initialized",
            processor_count=len(self._processors)
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
            self.logger.error(
                "processor_not_initialized",
                record_type=record_type
            )
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
