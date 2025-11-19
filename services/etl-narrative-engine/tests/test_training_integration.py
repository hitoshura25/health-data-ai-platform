"""
Integration tests for Module 4: Training Data Output.

These tests require MinIO running:
    docker-compose up -d minio

5 integration tests verify:
- End-to-end training data generation
- JSONL file creation and appending
- S3 storage structure (multiple domains)
- Deduplication across multiple runs
- JSONL format validity
"""

import json
import os
from datetime import UTC, datetime

import aioboto3
import pytest

from src.consumer.deduplication import SQLiteDeduplicationStore
from src.output.training_deduplicator import TrainingDeduplicator
from src.output.training_formatter import TrainingDataFormatter


@pytest.fixture(scope="module")
def s3_config():
    """S3/MinIO configuration for integration tests"""
    return {
        'endpoint_url': os.getenv('ETL_S3_ENDPOINT_URL', 'http://localhost:9000'),
        'access_key': os.getenv('ETL_S3_ACCESS_KEY', 'minioadmin'),
        'secret_key': os.getenv('ETL_S3_SECRET_KEY', 'minioadmin'),
        'bucket_name': os.getenv('ETL_S3_BUCKET_NAME', 'health-data'),
        'region': 'us-east-1',
    }


@pytest.fixture
async def s3_client(s3_config):
    """Create aioboto3 S3 client for testing"""
    session = aioboto3.Session()
    async with session.client(
        's3',
        endpoint_url=s3_config['endpoint_url'],
        aws_access_key_id=s3_config['access_key'],
        aws_secret_access_key=s3_config['secret_key'],
        region_name=s3_config['region'],
        use_ssl=False
    ) as client:
        # Ensure bucket exists - catch specific bucket already exists exceptions
        try:
            await client.create_bucket(Bucket=s3_config['bucket_name'])
        except client.exceptions.BucketAlreadyOwnedByYou:
            pass  # Bucket already exists and we own it - this is fine
        except client.exceptions.BucketAlreadyExists:
            pass  # Bucket already exists - this is fine for integration tests
        except Exception as e:
            # For other exceptions during bucket creation, log but don't fail
            # This handles cases where bucket might exist from previous test runs
            import logging
            logging.debug(f"Bucket creation issue (may already exist): {e}")
            pass

        yield client


@pytest.fixture
async def dedup_store():
    """Create in-memory SQLite deduplication store for testing"""
    store = SQLiteDeduplicationStore(
        db_path=":memory:",
        retention_hours=168
    )
    await store.initialize()
    yield store
    await store.close()


@pytest.fixture
def training_formatter(s3_client, s3_config):
    """Create training formatter instance"""
    return TrainingDataFormatter(
        s3_client=s3_client,
        bucket_name=s3_config['bucket_name'],
        training_prefix='training/',
        include_metadata=True
    )


@pytest.fixture
def training_deduplicator(dedup_store):
    """Create training deduplicator instance"""
    return TrainingDeduplicator(dedup_store=dedup_store)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_training_output(training_formatter, s3_client, s3_config):
    """Test complete training output pipeline"""
    narrative = (
        "Blood glucose data shows 450 readings over 30-day period with mean of 142.3 mg/dL. "
        "Glucose control is moderate with variability (CV 38%) and 62% time in target range."
    )

    source_metadata = {
        'bucket': s3_config['bucket_name'],
        'key': 'raw/BloodGlucoseRecord/2025/11/test_integration.avro',
        'record_type': 'BloodGlucoseRecord',
        'user_id': 'integration_test_user',
        'correlation_id': 'test-integration-001'
    }

    processing_metadata = {
        'duration': 2.3,
        'record_count': 450,
        'quality_score': 0.95,
        'clinical_insights': {
            'control_status': 'fair',
            'hypoglycemic_events': 3,
            'hyperglycemic_events': 45,
            'total_readings': 450
        }
    }

    # Generate training output
    success = await training_formatter.generate_training_output(
        narrative, source_metadata, processing_metadata
    )

    assert success is True

    # Verify file was created in S3
    # Expected key: training/metabolic_diabetes/{year}/{month}/health_journal_{year}_{month}.jsonl
    now = datetime.now(UTC)
    expected_key = (
        f"training/metabolic_diabetes/{now.year}/"
        f"{now.month:02d}/health_journal_{now.year}_{now.month:02d}.jsonl"
    )

    # Download and verify JSONL file
    response = await s3_client.get_object(
        Bucket=s3_config['bucket_name'],
        Key=expected_key
    )

    async with response['Body'] as stream:
        content = await stream.read()

    # Parse JSONL
    lines = content.decode('utf-8').strip().split('\n')
    assert len(lines) >= 1

    # Find our entry (might be multiple if tests run multiple times)
    found = False
    for line in lines:
        training_example = json.loads(line)

        if training_example['metadata']['correlation_id'] == 'test-integration-001':
            found = True

            # Validate structure
            assert 'instruction' in training_example
            assert 'input' in training_example
            assert 'output' in training_example
            assert 'metadata' in training_example

            # Validate instruction
            assert 'blood glucose' in training_example['instruction'].lower()
            assert 'analyze' in training_example['instruction'].lower()

            # Validate input
            assert '450' in training_example['input']

            # Validate output
            assert training_example['output'] == narrative

            # Validate metadata
            metadata = training_example['metadata']
            assert metadata['record_type'] == 'BloodGlucoseRecord'
            assert metadata['user_id'] == 'integration_test_user'
            assert metadata['quality_score'] == 0.95
            assert metadata['record_count'] == 450
            assert metadata['health_domain'] == 'metabolic_diabetes'
            assert 'clinical_insights' in metadata
            assert metadata['clinical_insights']['total_readings'] == 450

            break

    assert found, "Training example not found in JSONL file"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_training_output_appending(training_formatter, s3_client, s3_config):
    """Test appending multiple training examples to same file"""
    # Generate first example
    narrative1 = "First blood glucose reading."
    source_metadata1 = {
        'bucket': s3_config['bucket_name'],
        'key': 'raw/BloodGlucoseRecord/test1.avro',
        'record_type': 'BloodGlucoseRecord',
        'user_id': 'user1',
        'correlation_id': 'append-test-001'
    }
    processing_metadata1 = {
        'duration': 1.0,
        'record_count': 100,
        'quality_score': 0.90,
        'clinical_insights': {'total_readings': 100}
    }

    success1 = await training_formatter.generate_training_output(
        narrative1, source_metadata1, processing_metadata1
    )
    assert success1 is True

    # Generate second example (same month, same record type)
    narrative2 = "Second blood glucose reading."
    source_metadata2 = {
        'bucket': s3_config['bucket_name'],
        'key': 'raw/BloodGlucoseRecord/test2.avro',
        'record_type': 'BloodGlucoseRecord',
        'user_id': 'user2',
        'correlation_id': 'append-test-002'
    }
    processing_metadata2 = {
        'duration': 1.5,
        'record_count': 200,
        'quality_score': 0.85,
        'clinical_insights': {'total_readings': 200}
    }

    success2 = await training_formatter.generate_training_output(
        narrative2, source_metadata2, processing_metadata2
    )
    assert success2 is True

    # Verify both examples are in the file
    now = datetime.now(UTC)
    expected_key = (
        f"training/metabolic_diabetes/{now.year}/"
        f"{now.month:02d}/health_journal_{now.year}_{now.month:02d}.jsonl"
    )

    response = await s3_client.get_object(
        Bucket=s3_config['bucket_name'],
        Key=expected_key
    )

    async with response['Body'] as stream:
        content = await stream.read()

    lines = content.decode('utf-8').strip().split('\n')

    # Find both examples
    correlation_ids = set()
    for line in lines:
        example = json.loads(line)
        correlation_ids.add(example['metadata']['correlation_id'])

    assert 'append-test-001' in correlation_ids
    assert 'append-test-002' in correlation_ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_training_output_multiple_domains(training_formatter, s3_client, s3_config):
    """Test training output across different health domains"""
    # Blood glucose (metabolic_diabetes)
    await training_formatter.generate_training_output(
        narrative="Blood glucose test.",
        source_metadata={
            'bucket': s3_config['bucket_name'],
            'key': 'test_glucose.avro',
            'record_type': 'BloodGlucoseRecord',
            'user_id': 'test',
            'correlation_id': 'domain-test-glucose'
        },
        processing_metadata={
            'duration': 1.0,
            'record_count': 100,
            'quality_score': 0.90,
            'clinical_insights': {}
        }
    )

    # Heart rate (cardiovascular_fitness)
    await training_formatter.generate_training_output(
        narrative="Heart rate test.",
        source_metadata={
            'bucket': s3_config['bucket_name'],
            'key': 'test_heart.avro',
            'record_type': 'HeartRateRecord',
            'user_id': 'test',
            'correlation_id': 'domain-test-heart'
        },
        processing_metadata={
            'duration': 1.0,
            'record_count': 200,
            'quality_score': 0.95,
            'clinical_insights': {}
        }
    )

    # Verify separate files for each domain
    now = datetime.now(UTC)

    # Check metabolic_diabetes file
    glucose_key = (
        f"training/metabolic_diabetes/{now.year}/"
        f"{now.month:02d}/health_journal_{now.year}_{now.month:02d}.jsonl"
    )
    glucose_response = await s3_client.get_object(
        Bucket=s3_config['bucket_name'],
        Key=glucose_key
    )
    async with glucose_response['Body'] as stream:
        glucose_content = await stream.read()
    assert b'domain-test-glucose' in glucose_content

    # Check cardiovascular_fitness file
    heart_key = (
        f"training/cardiovascular_fitness/{now.year}/"
        f"{now.month:02d}/health_journal_{now.year}_{now.month:02d}.jsonl"
    )
    heart_response = await s3_client.get_object(
        Bucket=s3_config['bucket_name'],
        Key=heart_key
    )
    async with heart_response['Body'] as stream:
        heart_content = await stream.read()
    assert b'domain-test-heart' in heart_content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_training_deduplication(
    training_formatter,
    training_deduplicator,
    s3_client,
    s3_config
):
    """Test deduplication prevents duplicate training examples"""
    narrative = "Unique narrative for dedup test."
    source_metadata = {
        'bucket': s3_config['bucket_name'],
        'key': 'raw/BloodGlucoseRecord/dedup_test.avro',
        'record_type': 'BloodGlucoseRecord',
        'user_id': 'dedup_test',
        'correlation_id': 'dedup-test-001'
    }
    processing_metadata = {
        'duration': 1.0,
        'record_count': 100,
        'quality_score': 0.90,
        'clinical_insights': {}
    }

    # Generate content hash
    content_hash = training_formatter.generate_content_hash(
        narrative,
        source_metadata['key']
    )

    # First attempt should not be duplicate
    is_dup_before = await training_deduplicator.is_duplicate(content_hash)
    assert is_dup_before is False

    # Generate training output
    success = await training_formatter.generate_training_output(
        narrative, source_metadata, processing_metadata
    )
    assert success is True

    # Mark as processed
    await training_deduplicator.mark_as_processed(
        content_hash,
        metadata={
            'record_type': 'BloodGlucoseRecord',
            'correlation_id': 'dedup-test-001',
            'user_id': 'dedup_test',
            'source_key': source_metadata['key'],
            'source_bucket': source_metadata['bucket']
        }
    )

    # Second attempt should be duplicate
    is_dup_after = await training_deduplicator.is_duplicate(content_hash)
    assert is_dup_after is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_jsonl_format_validity(training_formatter, s3_client, s3_config):
    """Test that all generated JSONL is valid and parseable"""
    # Generate multiple examples
    for i in range(5):
        await training_formatter.generate_training_output(
            narrative=f"Test narrative {i}",
            source_metadata={
                'bucket': s3_config['bucket_name'],
                'key': f'test_{i}.avro',
                'record_type': 'StepsRecord',
                'user_id': f'user{i}',
                'correlation_id': f'jsonl-test-{i:03d}'
            },
            processing_metadata={
                'duration': 1.0,
                'record_count': 100,
                'quality_score': 0.90,
                'clinical_insights': {}
            }
        )

    # Read the file
    now = datetime.now(UTC)
    key = (
        f"training/physical_activity/{now.year}/"
        f"{now.month:02d}/health_journal_{now.year}_{now.month:02d}.jsonl"
    )

    response = await s3_client.get_object(
        Bucket=s3_config['bucket_name'],
        Key=key
    )

    async with response['Body'] as stream:
        content = await stream.read()

    # Parse every line
    lines = content.decode('utf-8').strip().split('\n')
    valid_examples = 0

    for line in lines:
        if not line.strip():
            continue

        # Should be valid JSON
        example = json.loads(line)

        # Should have required fields
        assert 'instruction' in example
        assert 'input' in example
        assert 'output' in example

        # If includes metadata, validate structure
        if 'metadata' in example:
            metadata = example['metadata']
            assert 'record_type' in metadata
            assert 'processing_timestamp' in metadata
            assert 'quality_score' in metadata
            assert 'health_domain' in metadata

        valid_examples += 1

    assert valid_examples >= 5
