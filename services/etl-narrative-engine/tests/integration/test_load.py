"""
Phase 5: Load and Performance Tests

These tests verify the ETL pipeline can handle concurrent processing
and meet performance requirements.

Requirements:
- Docker services running: MinIO, RabbitMQ
- Sample Avro files available

Run with:
    docker-compose up -d minio rabbitmq
    pytest tests/integration/test_load.py -v -m integration
"""

import asyncio
import json
import os
import time
from pathlib import Path
from uuid import uuid4

import aio_pika
import aioboto3
import psutil
import pytest

from src.consumer.deduplication import SQLiteDeduplicationStore


@pytest.fixture(scope="module")
def sample_files_dir():
    """Get path to sample Avro files"""
    project_root = Path(__file__).parent.parent.parent.parent.parent
    sample_dir = project_root / "docs" / "sample-avro-files"
    if not sample_dir.exists():
        pytest.skip(f"Sample files directory not found: {sample_dir}")
    return sample_dir


@pytest.fixture(scope="module")
def sample_files(sample_files_dir):
    """Get sample Avro files"""
    files = list(sample_files_dir.glob("*.avro"))
    if len(files) == 0:
        pytest.skip("No sample files found")
    return files


@pytest.fixture(scope="module")
def s3_config():
    """S3/MinIO configuration"""
    return {
        'endpoint_url': os.getenv('ETL_S3_ENDPOINT_URL', 'http://localhost:9000'),
        'access_key': os.getenv('ETL_S3_ACCESS_KEY', 'minioadmin'),
        'secret_key': os.getenv('ETL_S3_SECRET_KEY', 'minioadmin'),
        'bucket_name': os.getenv('ETL_S3_BUCKET_NAME', 'health-data'),
        'region': 'us-east-1',
    }


@pytest.fixture(scope="module")
def rabbitmq_url():
    """RabbitMQ connection URL"""
    return os.getenv('ETL_RABBITMQ_URL', 'amqp://guest:guest@localhost:5672')


@pytest.fixture
async def s3_client(s3_config):
    """Create S3 client for testing"""
    session = aioboto3.Session()
    async with session.client(
        's3',
        endpoint_url=s3_config['endpoint_url'],
        aws_access_key_id=s3_config['access_key'],
        aws_secret_access_key=s3_config['secret_key'],
        region_name=s3_config['region'],
        use_ssl=False
    ) as client:
        # Ensure bucket exists - handle already exists scenarios
        try:  # noqa: SIM105
            await client.create_bucket(Bucket=s3_config['bucket_name'])
        except (
            client.exceptions.BucketAlreadyOwnedByYou,
            client.exceptions.BucketAlreadyExists
        ):
            pass  # Bucket already exists, safe to continue
        yield client


@pytest.fixture
async def rabbitmq_connection(rabbitmq_url):
    """Create RabbitMQ connection"""
    try:
        connection = await aio_pika.connect_robust(rabbitmq_url)
        yield connection
        await connection.close()
    except Exception as e:
        pytest.skip(f"RabbitMQ not available: {e}")


@pytest.fixture
async def dedup_store():
    """Create in-memory deduplication store"""
    store = SQLiteDeduplicationStore(
        db_path=":memory:",
        retention_hours=168
    )
    await store.initialize()
    yield store
    await store.close()


async def upload_file_concurrent(
    s3_client,
    bucket: str,
    key: str,
    file_path: Path,
    semaphore: asyncio.Semaphore
):
    """Upload file to S3 with concurrency control"""
    async with semaphore:
        with open(file_path, 'rb') as f:
            file_content = f.read()
            await s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=file_content
            )
            return len(file_content)


async def publish_message_concurrent(
    rabbitmq_connection,
    queue_name: str,
    message_data: dict,
    semaphore: asyncio.Semaphore
):
    """Publish message to RabbitMQ with concurrency control"""
    async with semaphore, rabbitmq_connection.channel() as channel:
        await channel.declare_queue(queue_name, durable=True)
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message_data).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key=queue_name
        )


async def process_message_concurrent(
    s3_client,
    bucket: str,
    s3_key: str,
    dedup_store,
    idempotency_key: str,
    semaphore: asyncio.Semaphore
):
    """Simulate message processing with concurrency control"""
    async with semaphore:
        # Check deduplication
        if await dedup_store.is_already_processed(idempotency_key):
            return {'status': 'duplicate', 'key': s3_key}

        # Mark as started
        message_data = {'key': s3_key, 'bucket': bucket}
        await dedup_store.mark_processing_started(message_data, idempotency_key)

        try:
            # Download file (simulating processing)
            response = await s3_client.get_object(Bucket=bucket, Key=s3_key)
            content = await response['Body'].read()

            # Simulate processing delay
            await asyncio.sleep(0.1)

            # Mark as completed
            await dedup_store.mark_processing_completed(
                idempotency_key,
                processing_time=0.1,
                records_processed=len(content) // 100,
                narrative="",
                quality_score=1.0
            )

            return {
                'status': 'success',
                'key': s3_key,
                'size': len(content)
            }
        except Exception as e:
            await dedup_store.mark_processing_failed(
                idempotency_key,
                error_message=str(e),
                error_type=type(e).__name__
            )
            return {'status': 'failed', 'key': s3_key, 'error': str(e)}


def extract_record_type(filename: str) -> str:
    """Extract record type from filename"""
    return filename.split('_')[0]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_file_uploads(sample_files, s3_client, s3_config):
    """
    Test concurrent file uploads to S3

    Verifies system can handle multiple simultaneous uploads
    """
    bucket = s3_config['bucket_name']
    concurrency_limit = 10
    semaphore = asyncio.Semaphore(concurrency_limit)

    # Create upload tasks
    upload_tasks = []
    for sample_file in sample_files[:20]:  # Test with 20 files
        record_type = extract_record_type(sample_file.name)
        s3_key = f"raw/{record_type}/load_test/{uuid4().hex}.avro"

        task = upload_file_concurrent(
            s3_client, bucket, s3_key, sample_file, semaphore
        )
        upload_tasks.append(task)

    # Execute all uploads concurrently
    start_time = time.time()
    results = await asyncio.gather(*upload_tasks, return_exceptions=True)
    duration = max(time.time() - start_time, 0.001)  # Guard against division by zero

    # Count successes and failures
    successes = sum(1 for r in results if isinstance(r, int))
    failures = sum(1 for r in results if isinstance(r, Exception))

    print("\n⚡ Concurrent Upload Results:")
    print(f"  - Total uploads: {len(upload_tasks)}")
    print(f"  - Successful: {successes}")
    print(f"  - Failed: {failures}")
    print(f"  - Duration: {duration:.2f}s")
    print(f"  - Throughput: {successes/duration:.1f} uploads/sec")

    assert successes > 0, "No successful uploads"
    assert failures == 0, f"{failures} uploads failed"

    print("✅ Concurrent upload test passed!")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_message_publishing(
    sample_files,
    rabbitmq_connection
):
    """
    Test concurrent message publishing to RabbitMQ

    Verifies message queue can handle burst traffic
    """
    queue_name = 'load_test_concurrent_publish'
    concurrency_limit = 20
    semaphore = asyncio.Semaphore(concurrency_limit)

    # Create publish tasks
    publish_tasks = []
    for i in range(100):  # Publish 100 messages
        message_data = {
            "message_id": str(uuid4()),
            "correlation_id": f"load_test_{i}",
            "user_id": "load_test_user",
            "bucket": "health-data",
            "key": f"raw/test/message_{i}.avro",
            "record_type": "BloodGlucoseRecord",
            "idempotency_key": f"load_test_{i}",
            "priority": "normal",
            "retry_count": 0
        }

        task = publish_message_concurrent(
            rabbitmq_connection, queue_name, message_data, semaphore
        )
        publish_tasks.append(task)

    # Execute all publishes concurrently
    start_time = time.time()
    results = await asyncio.gather(*publish_tasks, return_exceptions=True)
    duration = max(time.time() - start_time, 0.001)  # Guard against division by zero

    # Count successes
    failures = sum(1 for r in results if isinstance(r, Exception))
    successes = len(results) - failures

    print("\n📨 Concurrent Publish Results:")
    print(f"  - Total messages: {len(publish_tasks)}")
    print(f"  - Successful: {successes}")
    print(f"  - Failed: {failures}")
    print(f"  - Duration: {duration:.2f}s")
    print(f"  - Throughput: {successes/duration:.0f} messages/sec")

    assert successes == len(publish_tasks), "Some publishes failed"

    print("✅ Concurrent publish test passed!")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_message_processing(
    sample_files,
    s3_client,
    s3_config,
    dedup_store
):
    """
    Test concurrent message processing

    Requirement: Process 100 messages concurrently without errors
    """
    bucket = s3_config['bucket_name']
    concurrency_limit = 10
    semaphore = asyncio.Semaphore(concurrency_limit)

    # Upload files first
    uploaded_keys = []
    for sample_file in sample_files[:20]:
        record_type = extract_record_type(sample_file.name)
        s3_key = f"raw/{record_type}/concurrent_test/{uuid4().hex}.avro"

        with open(sample_file, 'rb') as f:
            await s3_client.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=f.read()
            )
        uploaded_keys.append(s3_key)

    # Create processing tasks
    processing_tasks = []
    for s3_key in uploaded_keys:
        idempotency_key = f"{bucket}:{s3_key}"

        task = process_message_concurrent(
            s3_client, bucket, s3_key, dedup_store, idempotency_key, semaphore
        )
        processing_tasks.append(task)

    # Execute all processing concurrently
    start_time = time.time()
    results = await asyncio.gather(*processing_tasks)
    duration = max(time.time() - start_time, 0.001)  # Guard against division by zero

    # Analyze results
    success_count = sum(1 for r in results if r['status'] == 'success')
    failed_count = sum(1 for r in results if r['status'] == 'failed')
    duplicate_count = sum(1 for r in results if r['status'] == 'duplicate')

    print("\n🔄 Concurrent Processing Results:")
    print(f"  - Total tasks: {len(processing_tasks)}")
    print(f"  - Successful: {success_count}")
    print(f"  - Failed: {failed_count}")
    print(f"  - Duplicates: {duplicate_count}")
    print(f"  - Duration: {duration:.2f}s")
    print(f"  - Throughput: {success_count/duration:.1f} tasks/sec")

    assert success_count > 0, "No successful processing"
    assert failed_count == 0, f"{failed_count} tasks failed"

    # Test concurrent processing with duplicates
    print("\n🔁 Testing duplicate detection under load...")

    # Process same files again
    reprocess_tasks = []
    for s3_key in uploaded_keys[:10]:
        idempotency_key = f"{bucket}:{s3_key}"
        task = process_message_concurrent(
            s3_client, bucket, s3_key, dedup_store, idempotency_key, semaphore
        )
        reprocess_tasks.append(task)

    reprocess_results = await asyncio.gather(*reprocess_tasks)
    duplicate_detected = sum(1 for r in reprocess_results if r['status'] == 'duplicate')

    print(f"  - Reprocessing attempts: {len(reprocess_tasks)}")
    print(f"  - Duplicates detected: {duplicate_detected}")

    assert duplicate_detected == len(reprocess_tasks), "Deduplication failed under load"

    print("✅ Concurrent processing test passed!")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_throughput_benchmark(
    sample_files,
    s3_client,
    s3_config,
    dedup_store
):
    """
    Throughput benchmark: Measure maximum processing speed

    Target: Process as many files as possible in 10 seconds
    """
    bucket = s3_config['bucket_name']
    test_duration = 10  # seconds
    concurrency_limit = 15
    semaphore = asyncio.Semaphore(concurrency_limit)

    # Upload test files
    uploaded_keys = []
    for sample_file in sample_files * 5:  # Repeat files to get more data
        record_type = extract_record_type(sample_file.name)
        s3_key = f"raw/{record_type}/throughput_test/{uuid4().hex}.avro"

        with open(sample_file, 'rb') as f:
            await s3_client.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=f.read()
            )
        uploaded_keys.append(s3_key)

    print(f"\n⚡ Throughput Benchmark (target: {test_duration}s)...")
    print(f"  - Test files available: {len(uploaded_keys)}")

    # Process files until time limit
    start_time = time.time()
    processed_count = 0
    total_bytes = 0

    processing_tasks = []
    for s3_key in uploaded_keys:
        # Intentionally bypass deduplication with unique key to measure raw processing throughput
        # Note: Production behavior uses bucket:key without random UUID for proper deduplication
        idempotency_key = f"{bucket}:{s3_key}_{uuid4().hex}"
        task = process_message_concurrent(
            s3_client, bucket, s3_key, dedup_store, idempotency_key, semaphore
        )
        processing_tasks.append(task)

    # Process in batches
    batch_size = 20
    for i in range(0, len(processing_tasks), batch_size):
        if time.time() - start_time >= test_duration:
            break

        batch = processing_tasks[i:i+batch_size]
        batch_results = await asyncio.gather(*batch)

        for result in batch_results:
            if result['status'] == 'success':
                processed_count += 1
                total_bytes += result.get('size', 0)

    duration = max(time.time() - start_time, 0.001)  # Guard against division by zero
    throughput = processed_count / duration
    megabytes_per_sec = (total_bytes / 1024 / 1024) / duration

    print("\n📊 Throughput Results:")
    print(f"  - Duration: {duration:.2f}s")
    print(f"  - Files processed: {processed_count}")
    print(f"  - Throughput: {throughput:.1f} files/sec")
    print(f"  - Data processed: {total_bytes/1024/1024:.2f} MB")
    print(f"  - Data throughput: {megabytes_per_sec:.2f} MB/sec")

    assert processed_count > 10, f"Too few files processed: {processed_count}"
    assert throughput > 1.0, f"Throughput too low: {throughput:.1f} files/sec"

    print("✅ Throughput benchmark passed!")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stress_test_100_messages(
    sample_files,
    s3_client,
    s3_config,
    rabbitmq_connection,
    dedup_store
):
    """
    Stress test: Process 100 messages concurrently

    This is the Phase 5 requirement for load testing
    """
    bucket = s3_config['bucket_name']
    queue_name = 'stress_test_queue'
    num_messages = 100
    concurrency_limit = 15
    semaphore = asyncio.Semaphore(concurrency_limit)

    print(f"\n🚀 Stress Test: {num_messages} concurrent messages")

    # Step 1: Upload files
    print("  📤 Uploading test files...")
    upload_tasks = []
    for i in range(num_messages):
        sample_file = sample_files[i % len(sample_files)]
        record_type = extract_record_type(sample_file.name)
        s3_key = f"raw/{record_type}/stress_test/{uuid4().hex}.avro"

        task = upload_file_concurrent(s3_client, bucket, s3_key, sample_file, semaphore)
        upload_tasks.append((s3_key, task))

    upload_results = await asyncio.gather(*[t for _, t in upload_tasks])
    uploaded_keys = [k for k, _ in upload_tasks]

    print(f"    ✓ Uploaded {len(upload_results)} files")

    # Step 2: Publish messages
    print("  📨 Publishing messages...")
    publish_tasks = []
    for i, s3_key in enumerate(uploaded_keys):
        record_type = s3_key.split('/')[1]
        message_data = {
            "message_id": str(uuid4()),
            "correlation_id": f"stress_test_{i}",
            "user_id": "stress_test_user",
            "bucket": bucket,
            "key": s3_key,
            "record_type": record_type,
            "idempotency_key": f"{bucket}:{s3_key}",
            "priority": "normal",
            "retry_count": 0
        }
        task = publish_message_concurrent(
            rabbitmq_connection, queue_name, message_data, semaphore
        )
        publish_tasks.append(task)

    await asyncio.gather(*publish_tasks)
    print(f"    ✓ Published {len(publish_tasks)} messages")

    # Step 3: Simulate processing
    print("  ⚙️  Processing messages...")
    processing_start = time.time()

    process_tasks = []
    for s3_key in uploaded_keys:
        idempotency_key = f"{bucket}:{s3_key}"
        task = process_message_concurrent(
            s3_client, bucket, s3_key, dedup_store, idempotency_key, semaphore
        )
        process_tasks.append(task)

    process_results = await asyncio.gather(*process_tasks)
    processing_duration = time.time() - processing_start

    # Analyze results
    success_count = sum(1 for r in process_results if r['status'] == 'success')
    failed_count = sum(1 for r in process_results if r['status'] == 'failed')

    print("\n📈 Stress Test Results:")
    print(f"  - Messages sent: {num_messages}")
    print(f"  - Successfully processed: {success_count}")
    print(f"  - Failed: {failed_count}")
    print(f"  - Processing time: {processing_duration:.2f}s")
    print(f"  - Throughput: {success_count/processing_duration:.1f} messages/sec")

    # Assertions
    assert success_count >= num_messages * 0.95, f"Too many failures: {failed_count}/{num_messages}"
    assert processing_duration < 60, f"Processing too slow: {processing_duration:.2f}s"

    print("✅ Stress test passed!")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_memory_efficiency(sample_files, s3_client, s3_config):
    """
    Test memory efficiency: Process many files without memory leaks
    """
    bucket = s3_config['bucket_name']
    process = psutil.Process(os.getpid())

    # Measure initial memory
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    # Process 50 files
    for i in range(50):
        sample_file = sample_files[i % len(sample_files)]
        record_type = extract_record_type(sample_file.name)
        s3_key = f"raw/{record_type}/memory_test/{uuid4().hex}.avro"

        # Upload
        with open(sample_file, 'rb') as f:
            await s3_client.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=f.read()
            )

        # Download (simulating processing)
        response = await s3_client.get_object(Bucket=bucket, Key=s3_key)
        _ = await response['Body'].read()

    # Measure final memory
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory

    print("\n💾 Memory Efficiency Test:")
    print(f"  - Initial memory: {initial_memory:.1f} MB")
    print(f"  - Final memory: {final_memory:.1f} MB")
    print(f"  - Increase: {memory_increase:.1f} MB")

    # Allow up to 100MB increase for 50 files
    assert memory_increase < 100, f"Excessive memory usage: {memory_increase:.1f} MB"

    print("✅ Memory efficiency test passed!")
