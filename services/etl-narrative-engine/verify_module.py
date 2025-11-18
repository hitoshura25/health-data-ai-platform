#!/usr/bin/env python3
"""
Quick verification script for Module 2 validation code.
Tests that all imports work and basic functionality is accessible.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    # Test imports
    print("Testing imports...")
    from validation import (
        CLINICAL_RANGES,
        DataQualityValidator,
        ValidationConfig,
        ValidationResult,
        get_all_ranges,
        get_clinical_range,
        is_value_in_range,
    )
    print("✓ All imports successful")

    # Test ValidationResult creation
    print("\nTesting ValidationResult...")
    result = ValidationResult(
        is_valid=True,
        quality_score=0.95
    )
    result.add_error("Test error")
    assert result.is_valid is False
    assert len(result.errors) == 1
    print("✓ ValidationResult works correctly")

    # Test ValidationConfig
    print("\nTesting ValidationConfig...")
    config = ValidationConfig()
    assert config.quality_threshold == 0.7
    config.validate_weights()
    print("✓ ValidationConfig works correctly")

    # Test clinical ranges
    print("\nTesting clinical ranges...")
    range_tuple = get_clinical_range('BloodGlucoseRecord', 'glucose_mg_dl')
    assert range_tuple == (20, 600)
    assert is_value_in_range(100, 'BloodGlucoseRecord', 'glucose_mg_dl') is True
    assert is_value_in_range(1000, 'BloodGlucoseRecord', 'glucose_mg_dl') is False
    all_ranges = get_all_ranges()
    assert len(all_ranges) == 6
    print("✓ Clinical ranges work correctly")

    # Test DataQualityValidator creation
    print("\nTesting DataQualityValidator...")
    validator = DataQualityValidator()
    assert validator.config.quality_threshold == 0.7
    print("✓ DataQualityValidator initializes correctly")

    print("\n" + "="*50)
    print("✅ ALL VERIFICATION CHECKS PASSED!")
    print("="*50)
    print("\nModule 2 is ready for integration.")

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("\nNote: Some dependencies may not be installed.")
    print("This is expected - tests will work when dependencies are installed.")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
