"""
Validation result data structures.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum


class ValidationSeverity(Enum):
    """Severity level of validation issues."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class ValidationError:
    """Individual validation error or warning."""

    field_name: str
    """Name of the field that failed validation"""

    error_message: str
    """Human-readable description of the validation issue"""

    severity: ValidationSeverity
    """Severity level of this validation issue"""

    error_code: Optional[str] = None
    """Machine-readable error code for automated handling"""

    current_value: Optional[Any] = None
    """Current value that failed validation"""

    expected_value: Optional[Any] = None
    """Expected value or range"""

    clinical_context: Optional[str] = None
    """Additional clinical context for health-related validations"""


@dataclass
class ValidationResult:
    """Result of validation operations on health data."""

    is_valid: bool
    """Whether the data passed all validation checks"""

    quality_score: float
    """Overall data quality score (0.0 - 1.0)"""

    errors: List[ValidationError]
    """List of validation errors and warnings"""

    metadata: Dict[str, Any]
    """Additional validation metadata"""

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def has_critical_errors(self) -> bool:
        """Check if there are any critical validation errors."""
        return any(error.severity == ValidationSeverity.CRITICAL for error in self.errors)

    def has_errors(self) -> bool:
        """Check if there are any errors (ERROR or CRITICAL severity)."""
        return any(
            error.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
            for error in self.errors
        )

    def get_errors_by_severity(self, severity: ValidationSeverity) -> List[ValidationError]:
        """Get all errors of a specific severity level."""
        return [error for error in self.errors if error.severity == severity]

    def get_clinical_warnings(self) -> List[ValidationError]:
        """Get validation errors with clinical context."""
        return [error for error in self.errors if error.clinical_context is not None]

    def add_error(self, error: ValidationError):
        """Add a validation error to the result."""
        self.errors.append(error)
        # Update is_valid if this is a critical error or error
        if error.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]:
            self.is_valid = False

    def merge_result(self, other: "ValidationResult"):
        """Merge another validation result into this one."""
        self.errors.extend(other.errors)
        self.is_valid = self.is_valid and other.is_valid
        # Take minimum quality score
        self.quality_score = min(self.quality_score, other.quality_score)
        # Merge metadata
        self.metadata.update(other.metadata)

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of validation results."""
        severity_counts = {}
        for severity in ValidationSeverity:
            severity_counts[severity.value] = len(self.get_errors_by_severity(severity))

        return {
            "is_valid": self.is_valid,
            "quality_score": self.quality_score,
            "total_errors": len(self.errors),
            "has_critical_errors": self.has_critical_errors(),
            "severity_breakdown": severity_counts,
            "clinical_warnings_count": len(self.get_clinical_warnings()),
        }