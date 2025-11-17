"""
Base clinical processor interface for ETL Narrative Engine.

All clinical processors (BloodGlucose, HeartRate, Sleep, etc.) must implement
this interface to be called by the message consumer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class ProcessingResult:
    """
    Result returned by clinical processors after processing health records.

    Attributes:
        success: Whether processing completed successfully
        narrative: Human-readable clinical narrative (None if failed)
        error_message: Error description (None if successful)
        processing_time_seconds: Time taken to process
        records_processed: Number of records processed
        quality_score: Data quality score (0.0 to 1.0)
        clinical_insights: Structured clinical insights (processor-specific)
    """
    success: bool
    narrative: str | None = None
    error_message: str | None = None
    processing_time_seconds: float = 0.0
    records_processed: int = 0
    quality_score: float = 1.0
    clinical_insights: dict[str, Any] | None = None


class BaseClinicalProcessor(ABC):
    """
    Abstract base class for all clinical data processors.

    Each health data type (BloodGlucose, HeartRate, Sleep, etc.) implements
    this interface to provide domain-specific processing logic.

    The consumer calls:
    1. initialize() once at startup
    2. process_with_clinical_insights() for each message
    """

    def __init__(self):
        """Initialize the processor"""
        self.logger = structlog.get_logger(processor=self.__class__.__name__)

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize processor-specific configurations.

        Called once during consumer startup. Use this to:
        - Load any required models or lookup tables
        - Set up clinical range validators
        - Initialize any stateful resources

        Raises:
            Exception: If initialization fails
        """
        pass

    @abstractmethod
    async def process_with_clinical_insights(
        self,
        records: list[dict[str, Any]],
        message_data: dict[str, Any],
        validation_result: Any
    ) -> ProcessingResult:
        """
        Process health records and generate clinical narrative.

        This is the main processing method called by the consumer for each
        message. Implementers should:
        1. Extract relevant fields from records
        2. Calculate clinical metrics (mean, std, time-in-range, etc.)
        3. Detect patterns and anomalies
        4. Generate human-readable narrative
        5. Return structured insights

        Args:
            records: List of health record dictionaries parsed from Avro
            message_data: Original message metadata from RabbitMQ
            validation_result: Data quality validation result from Module 2

        Returns:
            ProcessingResult with narrative and clinical insights

        Raises:
            ProcessingError: If processing fails
        """
        pass

    async def cleanup(self) -> None:
        """
        Cleanup processor resources.

        Called during graceful shutdown. Override if you need to:
        - Close connections
        - Flush buffers
        - Release resources
        """
        self.logger.info("processor_cleanup", processor=self.__class__.__name__)


class ProcessingError(Exception):
    """
    Base exception for processing errors.

    Note: For DataQualityError and SchemaError, import from:
        from ..consumer.error_recovery import DataQualityError, SchemaError
    """
    pass
