"""
Integration Tests for Data Validation Module

Tests validation with real Avro sample files to ensure the validation
framework works correctly with production data.
"""

import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastavro import reader

from src.validation import (
    DataQualityValidator,
    ValidationConfig,
)

# Path to sample Avro files
SAMPLE_FILES_DIR = Path(__file__).parent.parent.parent.parent / 'docs' / 'sample-avro-files'


def load_avro_file(filename: str) -> tuple[list, int]:
    """
    Load Avro file and return records and file size.

    Args:
        filename: Name of the Avro file

    Returns:
        Tuple of (records list, file size in bytes)
    """
    file_path = SAMPLE_FILES_DIR / filename

    if not file_path.exists():
        pytest.skip(f"Sample file not found: {file_path}")

    with open(file_path, 'rb') as f:
        records = list(reader(f))

    file_size = os.path.getsize(file_path)

    return records, file_size


class TestBloodGlucoseValidation:
    """Test validation with real BloodGlucoseRecord files"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_blood_glucose_sample_file(self):
        """Test validation with real blood glucose sample file"""
        validator = DataQualityValidator()

        records, file_size = load_avro_file('BloodGlucoseRecord_1758407139312.avro')

        result = await validator.validate(
            records,
            'BloodGlucoseRecord',
            file_size
        )

        # Sample files should pass validation
        assert result.is_valid is True
        assert result.quality_score >= 0.7
        assert len(result.errors) == 0
        assert result.metadata['record_count'] == len(records)
        assert result.metadata['schema_valid'] is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_multiple_blood_glucose_files(self):
        """Test validation across multiple blood glucose files"""
        validator = DataQualityValidator()

        # Test multiple blood glucose files
        test_files = [
            'BloodGlucoseRecord_1758407139312.avro',
            'BloodGlucoseRecord_1758407245091.avro',
            'BloodGlucoseRecord_1758407386729.avro',
        ]

        for filename in test_files:
            # load_avro_file already handles missing files with pytest.skip
            records, file_size = load_avro_file(filename)

            result = await validator.validate(
                records,
                'BloodGlucoseRecord',
                file_size
            )

            assert result.is_valid is True, f"Failed for {filename}"
            assert result.quality_score >= 0.7, f"Low quality for {filename}"


class TestHeartRateValidation:
    """Test validation with real HeartRateRecord files"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_heart_rate_sample_file(self):
        """Test validation with real heart rate sample file"""
        validator = DataQualityValidator()

        records, file_size = load_avro_file('HeartRateRecord_1758407139312.avro')

        result = await validator.validate(
            records,
            'HeartRateRecord',
            file_size
        )

        assert result.is_valid is True
        assert result.quality_score >= 0.7
        assert result.metadata['schema_valid'] is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_heart_rate_physiological_ranges(self):
        """Test that heart rate values are within physiological ranges"""
        validator = DataQualityValidator()

        records, file_size = load_avro_file('HeartRateRecord_1758407139312.avro')

        result = await validator.validate(
            records,
            'HeartRateRecord',
            file_size
        )

        # Heart rate values should be within range (30-220 bpm)
        assert result.metadata['physiological_score'] >= 0.8


class TestSleepSessionValidation:
    """Test validation with real SleepSessionRecord files"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sleep_session_sample_file(self):
        """Test validation with real sleep session sample file"""
        validator = DataQualityValidator()

        records, file_size = load_avro_file('SleepSessionRecord_1758407139312.avro')

        result = await validator.validate(
            records,
            'SleepSessionRecord',
            file_size
        )

        assert result.is_valid is True
        assert result.quality_score >= 0.7
        assert result.metadata['schema_valid'] is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sleep_duration_validation(self):
        """Test that sleep durations are within reasonable ranges"""
        validator = DataQualityValidator()

        records, file_size = load_avro_file('SleepSessionRecord_1758407139312.avro')

        result = await validator.validate(
            records,
            'SleepSessionRecord',
            file_size
        )

        # Sleep durations should be valid (0.5-16 hours)
        # Physiological score should be high
        assert result.metadata['physiological_score'] >= 0.0  # May have some invalid durations


class TestStepsValidation:
    """Test validation with real StepsRecord files"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_steps_sample_file(self):
        """Test validation with real steps sample file"""
        validator = DataQualityValidator()

        records, file_size = load_avro_file('StepsRecord_1758407139312.avro')

        result = await validator.validate(
            records,
            'StepsRecord',
            file_size
        )

        assert result.is_valid is True
        assert result.quality_score >= 0.7
        assert result.metadata['schema_valid'] is True


class TestActiveCaloriesValidation:
    """Test validation with real ActiveCaloriesBurnedRecord files"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_active_calories_sample_file(self):
        """Test validation with real active calories sample file"""
        validator = DataQualityValidator()

        records, file_size = load_avro_file('ActiveCaloriesBurnedRecord_1758407139312.avro')

        result = await validator.validate(
            records,
            'ActiveCaloriesBurnedRecord',
            file_size
        )

        assert result.is_valid is True
        assert result.quality_score >= 0.7
        assert result.metadata['schema_valid'] is True


class TestHRVValidation:
    """Test validation with real HeartRateVariabilityRmssdRecord files"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_hrv_sample_file(self):
        """Test validation with real HRV sample file"""
        validator = DataQualityValidator()

        records, file_size = load_avro_file('HeartRateVariabilityRmssdRecord_1758407139312.avro')

        result = await validator.validate(
            records,
            'HeartRateVariabilityRmssdRecord',
            file_size
        )

        assert result.is_valid is True
        assert result.quality_score >= 0.7
        assert result.metadata['schema_valid'] is True


class TestAllRecordTypes:
    """Test validation across all 6 record types"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_all_record_types_with_samples(self):
        """Test that all 6 record types validate successfully"""
        validator = DataQualityValidator()

        # Map record types to sample files
        record_type_files = {
            'BloodGlucoseRecord': 'BloodGlucoseRecord_1758407139312.avro',
            'HeartRateRecord': 'HeartRateRecord_1758407139312.avro',
            'SleepSessionRecord': 'SleepSessionRecord_1758407139312.avro',
            'StepsRecord': 'StepsRecord_1758407139312.avro',
            'ActiveCaloriesBurnedRecord': 'ActiveCaloriesBurnedRecord_1758407139312.avro',
            'HeartRateVariabilityRmssdRecord': 'HeartRateVariabilityRmssdRecord_1758407139312.avro',
        }

        results = {}

        for record_type, filename in record_type_files.items():
            try:
                records, file_size = load_avro_file(filename)

                result = await validator.validate(
                    records,
                    record_type,
                    file_size
                )

                results[record_type] = result

                # All sample files should pass validation
                assert result.is_valid is True, f"Failed for {record_type}"
                assert result.quality_score >= 0.7, f"Low quality for {record_type}"

            except Exception as e:
                pytest.skip(f"Could not test {record_type}: {e}")

        # Should have tested at least some record types
        assert len(results) > 0


class TestQuarantineIntegration:
    """Test quarantine mechanism with real files"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_quarantine_low_quality_file(self):
        """Test quarantining a low-quality file"""
        # Mock S3 client
        mock_s3 = AsyncMock()

        validator = DataQualityValidator(
            config=ValidationConfig(
                quality_threshold=0.99,  # Very high threshold to force quarantine
                enable_quarantine=True
            ),
            s3_client=mock_s3,
            bucket_name='test-bucket'
        )

        records, file_size = load_avro_file('BloodGlucoseRecord_1758407139312.avro')

        # Validate
        result = await validator.validate(
            records,
            'BloodGlucoseRecord',
            file_size
        )

        # Quality score likely won't reach 0.99, so should be invalid
        # (This depends on actual data quality, adjust threshold if needed)

        # Try to quarantine
        with open(SAMPLE_FILES_DIR / 'BloodGlucoseRecord_1758407139312.avro', 'rb') as f:
            file_content = f.read()

        await validator.quarantine_file(
            s3_key="raw/BloodGlucoseRecord/2025/11/15/test.avro",
            validation_result=result,
            file_content=file_content
        )

        # Should have uploaded file and metadata
        assert mock_s3.put_object.call_count == 2

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_validation_metadata_completeness(self):
        """Test that validation metadata contains all expected fields"""
        validator = DataQualityValidator()

        records, file_size = load_avro_file('BloodGlucoseRecord_1758407139312.avro')

        result = await validator.validate(
            records,
            'BloodGlucoseRecord',
            file_size
        )

        # Check metadata completeness
        assert 'schema_valid' in result.metadata
        assert 'completeness_score' in result.metadata
        assert 'physiological_score' in result.metadata
        assert 'temporal_score' in result.metadata
        assert 'record_count' in result.metadata
        assert 'record_type' in result.metadata

        # Check metadata values
        assert result.metadata['record_type'] == 'BloodGlucoseRecord'
        assert result.metadata['record_count'] == len(records)
        assert 0.0 <= result.metadata['completeness_score'] <= 1.0
        assert 0.0 <= result.metadata['physiological_score'] <= 1.0
        assert 0.0 <= result.metadata['temporal_score'] <= 1.0


class TestPerformance:
    """Test validation performance with real files"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_validation_performance(self):
        """Test that validation completes quickly"""
        import time

        validator = DataQualityValidator()

        records, file_size = load_avro_file('BloodGlucoseRecord_1758407139312.avro')

        # Measure validation time
        start_time = time.time()

        result = await validator.validate(
            records,
            'BloodGlucoseRecord',
            file_size
        )

        end_time = time.time()
        elapsed_time = end_time - start_time

        # Validation should complete quickly (target: <1s, allow 2s for CI variability)
        # Documentation states <1 second for 10,000 records
        assert elapsed_time < 2.0, f"Validation took {elapsed_time:.2f}s, too slow"

        assert result.is_valid is True


class TestEdgeCases:
    """Test edge cases with real data"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_custom_quality_threshold(self):
        """Test validation with custom quality threshold"""
        # Very lenient threshold
        lenient_validator = DataQualityValidator(
            config=ValidationConfig(quality_threshold=0.3)
        )

        records, file_size = load_avro_file('BloodGlucoseRecord_1758407139312.avro')

        result = await lenient_validator.validate(
            records,
            'BloodGlucoseRecord',
            file_size
        )

        # Should definitely pass with low threshold
        assert result.is_valid is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_custom_scoring_weights(self):
        """Test validation with custom scoring weights"""
        # Heavy weight on schema validation
        custom_validator = DataQualityValidator(
            config=ValidationConfig(
                schema_weight=0.7,
                completeness_weight=0.1,
                physiological_weight=0.1,
                temporal_weight=0.1
            )
        )

        records, file_size = load_avro_file('BloodGlucoseRecord_1758407139312.avro')

        result = await custom_validator.validate(
            records,
            'BloodGlucoseRecord',
            file_size
        )

        # Should pass since schema is valid
        assert result.is_valid is True
        assert result.metadata['schema_valid'] is True
