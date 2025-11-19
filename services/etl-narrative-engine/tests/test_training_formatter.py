"""
Unit tests for training data formatter (Module 4).

Tests cover:
- Instruction generation
- Health domain mapping
- S3 key generation
- JSONL formatting
- Content hashing
- Deduplication
"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.output.training_deduplicator import TrainingDeduplicator
from src.output.training_formatter import TrainingDataFormatter


class TestTrainingDataFormatter:
    """Test suite for TrainingDataFormatter"""

    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client"""
        client = AsyncMock()
        # Mock NoSuchKey exception as a proper exception class
        # This ensures isinstance() checks work correctly in the code
        client.exceptions = MagicMock()
        client.exceptions.NoSuchKey = type('NoSuchKey', (Exception,), {})
        return client

    @pytest.fixture
    def formatter(self, mock_s3_client):
        """Create formatter instance with mock S3 client"""
        return TrainingDataFormatter(
            s3_client=mock_s3_client,
            bucket_name='test-bucket',
            training_prefix='training/',
            include_metadata=True
        )

    def test_health_domain_mapping(self, formatter):
        """Test record type to health domain mapping"""
        assert formatter._get_health_domain('BloodGlucoseRecord') == 'metabolic_diabetes'
        assert formatter._get_health_domain('HeartRateRecord') == 'cardiovascular_fitness'
        assert formatter._get_health_domain('SleepSessionRecord') == 'sleep_wellness'
        assert formatter._get_health_domain('StepsRecord') == 'physical_activity'
        assert formatter._get_health_domain('ActiveCaloriesBurnedRecord') == 'physical_activity'
        assert formatter._get_health_domain('HeartRateVariabilityRmssdRecord') == 'cardiovascular_fitness'
        assert formatter._get_health_domain('UnknownRecord') == 'general_health'

    def test_instruction_generation_blood_glucose(self, formatter):
        """Test instruction generation for blood glucose"""
        instruction, input_text = formatter._generate_instruction_input(
            'BloodGlucoseRecord',
            {'clinical_insights': {'total_readings': 450}}
        )

        assert 'blood glucose' in instruction.lower()
        assert 'analyze' in instruction.lower()
        assert '450' in input_text

    def test_instruction_generation_heart_rate(self, formatter):
        """Test instruction generation for heart rate"""
        instruction, input_text = formatter._generate_instruction_input(
            'HeartRateRecord',
            {'clinical_insights': {'total_samples': 1200}}
        )

        assert 'heart rate' in instruction.lower()
        assert 'cardiovascular' in instruction.lower()
        assert '1200' in input_text

    def test_instruction_generation_sleep(self, formatter):
        """Test instruction generation for sleep"""
        instruction, input_text = formatter._generate_instruction_input(
            'SleepSessionRecord',
            {'clinical_insights': {}}
        )

        assert 'sleep' in instruction.lower()
        assert 'quality' in instruction.lower()

    def test_instruction_generation_unknown_type(self, formatter):
        """Test instruction generation for unknown record type"""
        instruction, input_text = formatter._generate_instruction_input(
            'UnknownRecord',
            {}
        )

        assert 'health data' in instruction.lower()
        assert 'clinical insights' in instruction.lower()

    @patch('src.output.training_formatter.datetime')
    def test_training_file_key_generation(self, mock_datetime, formatter):
        """Test S3 key generation for training files"""
        # Mock datetime to fixed value
        mock_now = datetime(2025, 11, 15, 10, 30, 0, tzinfo=UTC)
        mock_datetime.now.return_value = mock_now

        key = formatter._generate_training_file_key('BloodGlucoseRecord')

        assert key == 'training/metabolic_diabetes/2025/11/health_journal_2025_11.jsonl'

    @patch('src.output.training_formatter.datetime')
    def test_training_file_key_generation_cardiovascular(self, mock_datetime, formatter):
        """Test S3 key generation for cardiovascular domain"""
        mock_now = datetime(2025, 12, 1, 0, 0, 0, tzinfo=UTC)
        mock_datetime.now.return_value = mock_now

        key = formatter._generate_training_file_key('HeartRateRecord')

        assert key == 'training/cardiovascular_fitness/2025/12/health_journal_2025_12.jsonl'

    def test_content_hash_generation(self, formatter):
        """Test content hash generation"""
        narrative = "Blood glucose data shows good control."
        source_key = "raw/BloodGlucoseRecord/test.avro"

        hash1 = formatter.generate_content_hash(narrative, source_key)

        # Hash should be 64 characters (SHA-256 hex)
        assert len(hash1) == 64
        assert all(c in '0123456789abcdef' for c in hash1)

        # Same inputs should produce same hash
        hash2 = formatter.generate_content_hash(narrative, source_key)
        assert hash1 == hash2

        # Different narrative should produce different hash
        hash3 = formatter.generate_content_hash("Different narrative", source_key)
        assert hash1 != hash3

        # Different source key should produce different hash
        hash4 = formatter.generate_content_hash(narrative, "different_key.avro")
        assert hash1 != hash4

    @pytest.mark.asyncio
    async def test_generate_training_output_success(self, formatter, mock_s3_client):
        """Test successful training output generation"""
        narrative = "Blood glucose data shows 450 readings with mean of 142 mg/dL."
        source_metadata = {
            'bucket': 'health-data',
            'key': 'raw/BloodGlucoseRecord/test.avro',
            'record_type': 'BloodGlucoseRecord',
            'user_id': 'test_user',
            'correlation_id': 'test-123'
        }
        processing_metadata = {
            'duration': 2.3,
            'record_count': 450,
            'quality_score': 0.95,
            'clinical_insights': {'control_status': 'good'}
        }

        # Mock S3 get_object to raise NoSuchKey (file doesn't exist)
        mock_s3_client.get_object.side_effect = mock_s3_client.exceptions.NoSuchKey()

        success = await formatter.generate_training_output(
            narrative, source_metadata, processing_metadata
        )

        assert success is True

        # Verify put_object was called
        assert mock_s3_client.put_object.called
        put_call = mock_s3_client.put_object.call_args

        # Check S3 key
        assert 'metabolic_diabetes' in put_call.kwargs['Key']
        assert put_call.kwargs['Key'].endswith('.jsonl')

        # Check content type
        assert put_call.kwargs['ContentType'] == 'application/jsonl'

        # Parse and validate JSONL content
        jsonl_content = put_call.kwargs['Body'].decode('utf-8')
        lines = jsonl_content.strip().split('\n')
        assert len(lines) == 1

        training_example = json.loads(lines[0])
        assert 'instruction' in training_example
        assert 'input' in training_example
        assert 'output' in training_example
        assert training_example['output'] == narrative
        assert 'metadata' in training_example
        assert training_example['metadata']['record_type'] == 'BloodGlucoseRecord'
        assert training_example['metadata']['quality_score'] == 0.95

    @pytest.mark.asyncio
    async def test_generate_training_output_append_existing(self, formatter, mock_s3_client):
        """Test appending to existing JSONL file"""
        narrative = "New blood glucose reading."
        source_metadata = {
            'bucket': 'health-data',
            'key': 'raw/BloodGlucoseRecord/test2.avro',
            'record_type': 'BloodGlucoseRecord',
            'user_id': 'test_user',
            'correlation_id': 'test-456'
        }
        processing_metadata = {
            'duration': 1.5,
            'record_count': 200,
            'quality_score': 0.90,
            'clinical_insights': {}
        }

        # Mock existing JSONL content
        existing_line = json.dumps({'instruction': 'test', 'output': 'existing'}) + '\n'
        existing_content = existing_line.encode('utf-8')

        # Mock S3 get_object to return existing content
        mock_response = AsyncMock()
        mock_stream = AsyncMock()
        mock_stream.read = AsyncMock(return_value=existing_content)
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)
        mock_response.__getitem__ = lambda self, key: mock_stream if key == 'Body' else None
        mock_s3_client.get_object.return_value = mock_response

        success = await formatter.generate_training_output(
            narrative, source_metadata, processing_metadata
        )

        assert success is True

        # Verify content was appended
        put_call = mock_s3_client.put_object.call_args
        new_content = put_call.kwargs['Body']

        # Should contain both lines
        lines = new_content.decode('utf-8').strip().split('\n')
        assert len(lines) == 2

        # First line should be existing
        first_entry = json.loads(lines[0])
        assert first_entry['output'] == 'existing'

        # Second line should be new
        second_entry = json.loads(lines[1])
        assert second_entry['output'] == narrative

    @pytest.mark.asyncio
    async def test_generate_training_output_empty_narrative(self, formatter):
        """Test handling of empty narrative"""
        success = await formatter.generate_training_output(
            narrative="",
            source_metadata={'key': 'test.avro', 'record_type': 'BloodGlucoseRecord'},
            processing_metadata={}
        )

        assert success is False

    @pytest.mark.asyncio
    async def test_generate_training_output_without_metadata(self, mock_s3_client):
        """Test training output without metadata"""
        formatter = TrainingDataFormatter(
            s3_client=mock_s3_client,
            bucket_name='test-bucket',
            training_prefix='training/',
            include_metadata=False  # Disable metadata
        )

        narrative = "Test narrative"
        source_metadata = {
            'bucket': 'health-data',
            'key': 'test.avro',
            'record_type': 'StepsRecord',
            'user_id': 'test_user',
            'correlation_id': 'test-789'
        }
        processing_metadata = {
            'duration': 1.0,
            'record_count': 100,
            'quality_score': 0.85,
            'clinical_insights': {}
        }

        # Mock S3 to create new file
        mock_s3_client.get_object.side_effect = mock_s3_client.exceptions.NoSuchKey()

        success = await formatter.generate_training_output(
            narrative, source_metadata, processing_metadata
        )

        assert success is True

        # Verify JSONL doesn't include metadata
        put_call = mock_s3_client.put_object.call_args
        jsonl_content = put_call.kwargs['Body'].decode('utf-8')
        training_example = json.loads(jsonl_content.strip())

        assert 'instruction' in training_example
        assert 'output' in training_example
        assert 'metadata' not in training_example


class TestTrainingDeduplicator:
    """Test suite for TrainingDeduplicator"""

    @pytest.fixture
    def mock_dedup_store(self):
        """Create mock deduplication store"""
        store = AsyncMock()
        return store

    @pytest.fixture
    def deduplicator(self, mock_dedup_store):
        """Create deduplicator instance"""
        return TrainingDeduplicator(dedup_store=mock_dedup_store)

    def test_content_hash_generation(self, deduplicator):
        """Test content hash generation"""
        narrative = "Test narrative"
        source_key = "test.avro"

        hash1 = deduplicator.generate_content_hash(narrative, source_key)

        # Hash should be 64 characters (SHA-256 hex)
        assert len(hash1) == 64

        # Same inputs should produce same hash
        hash2 = deduplicator.generate_content_hash(narrative, source_key)
        assert hash1 == hash2

    def test_content_hash_empty_inputs(self, deduplicator):
        """Test content hash with empty inputs"""
        with pytest.raises(ValueError):
            deduplicator.generate_content_hash("", "key")

        with pytest.raises(ValueError):
            deduplicator.generate_content_hash("narrative", "")

    @pytest.mark.asyncio
    async def test_is_duplicate_true(self, deduplicator, mock_dedup_store):
        """Test duplicate detection when example exists"""
        content_hash = "abc123def456"
        mock_dedup_store.is_already_processed.return_value = True

        is_dup = await deduplicator.is_duplicate(content_hash)

        assert is_dup is True
        mock_dedup_store.is_already_processed.assert_called_once()
        call_key = mock_dedup_store.is_already_processed.call_args[0][0]
        assert call_key.startswith('training:')

    @pytest.mark.asyncio
    async def test_is_duplicate_false(self, deduplicator, mock_dedup_store):
        """Test duplicate detection when example is new"""
        content_hash = "abc123def456"
        mock_dedup_store.is_already_processed.return_value = False

        is_dup = await deduplicator.is_duplicate(content_hash)

        assert is_dup is False

    @pytest.mark.asyncio
    async def test_is_duplicate_error_handling(self, deduplicator, mock_dedup_store):
        """Test error handling in duplicate check"""
        content_hash = "abc123def456"
        mock_dedup_store.is_already_processed.side_effect = Exception("Store error")

        # Should return False on error (fail open)
        is_dup = await deduplicator.is_duplicate(content_hash)

        assert is_dup is False

    @pytest.mark.asyncio
    async def test_mark_as_processed(self, deduplicator, mock_dedup_store):
        """Test marking training example as processed"""
        content_hash = "abc123def456"
        metadata = {
            'record_type': 'BloodGlucoseRecord',
            'correlation_id': 'test-123',
            'user_id': 'test_user',
            'source_key': 'test.avro',
            'source_bucket': 'health-data'
        }

        await deduplicator.mark_as_processed(content_hash, metadata)

        mock_dedup_store.mark_processing_started.assert_called_once()
        call_args = mock_dedup_store.mark_processing_started.call_args

        # Verify training key prefix
        training_key = call_args[0][1]
        assert training_key.startswith('training:')
        assert content_hash in training_key

    @pytest.mark.asyncio
    async def test_mark_as_processed_error(self, deduplicator, mock_dedup_store):
        """Test error handling when marking as processed"""
        content_hash = "abc123def456"
        mock_dedup_store.mark_processing_started.side_effect = Exception("Store error")

        with pytest.raises(Exception, match="Store error"):
            await deduplicator.mark_as_processed(content_hash)
