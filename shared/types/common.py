"""
Common type definitions shared across all health record types.
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


@dataclass
class AvroDevice:
    """Device information for health data collection devices."""

    manufacturer: Optional[str] = None
    """Device manufacturer (e.g., Samsung, Oura, Dexcom)"""

    model: Optional[str] = None
    """Device model (e.g., Galaxy Watch 7, Oura Ring Gen 3, Stelo)"""

    type: Optional[str] = None
    """Device type classification (e.g., smartwatch, ring, cgm)"""


@dataclass
class AvroMetadata:
    """Common metadata structure for all health records from Android Health Connect."""

    id: str
    """Unique identifier for this health record"""

    data_origin_package_name: str
    """Package name of the app that originally created this data"""

    last_modified_time_epoch_millis: int
    """Last modification timestamp in epoch milliseconds"""

    client_record_id: Optional[str] = None
    """Optional client-provided record identifier"""

    client_record_version: int = 0
    """Version number for client record management"""

    device: Optional[AvroDevice] = None
    """Device information where this data was captured"""


# Validation helpers
def validate_epoch_timestamp(timestamp: int) -> bool:
    """Validate that timestamp is a reasonable epoch millisecond value."""
    # Check if timestamp is between 2020 and 2030 (reasonable health data range)
    min_timestamp = 1577836800000  # 2020-01-01 00:00:00 UTC
    max_timestamp = 1893456000000  # 2030-01-01 00:00:00 UTC
    return min_timestamp <= timestamp <= max_timestamp


def validate_device_info(device: Optional[AvroDevice]) -> bool:
    """Validate device information if provided."""
    if device is None:
        return True

    # Basic validation - at least one field should be populated
    return any([device.manufacturer, device.model, device.type])