"""
Validation Configuration

This module defines configuration settings for data validation.
"""

from pydantic import BaseModel, Field


class ValidationConfig(BaseModel):
    """Configuration for data quality validation"""

    # Quality thresholds
    quality_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum quality score for valid data (0.0 to 1.0)"
    )
    enable_quarantine: bool = Field(
        default=True,
        description="Enable quarantine for low-quality data"
    )

    # Scoring weights (must sum to 1.0)
    schema_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight for schema validation score"
    )
    completeness_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight for completeness score"
    )
    physiological_weight: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Weight for physiological range validation score"
    )
    temporal_weight: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Weight for temporal consistency score"
    )

    # File limits
    max_file_size_mb: int = Field(
        default=100,
        gt=0,
        description="Maximum file size in megabytes"
    )
    max_records_per_file: int = Field(
        default=100000,
        gt=0,
        description="Maximum number of records per file"
    )

    # Quarantine settings
    quarantine_prefix: str = Field(
        default="quarantine/",
        description="S3 prefix for quarantined files"
    )
    include_quarantine_metadata: bool = Field(
        default=True,
        description="Include metadata file when quarantining"
    )

    def validate_weights(self) -> None:
        """
        Validate that scoring weights sum to 1.0

        Raises:
            ValueError: If weights don't sum to 1.0
        """
        total = (
            self.schema_weight +
            self.completeness_weight +
            self.physiological_weight +
            self.temporal_weight
        )
        if not 0.99 <= total <= 1.01:  # Allow small floating point errors
            raise ValueError(
                f"Validation weights must sum to 1.0, got {total:.2f}"
            )

    class Config:
        """Pydantic configuration"""
        validate_assignment = True
