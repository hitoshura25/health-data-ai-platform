import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from prometheus_client import start_http_server
from monitoring.metrics import BUCKET_USAGE_BYTES, BUCKET_OBJECTS
from storage.client import SecureMinIOClient
from config.settings import settings

async def update_metrics():
    """Update the bucket metrics periodically."""
    client = SecureMinIOClient(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
        region=settings.minio_region,
    )

    try:
        stats = await client.get_bucket_stats(settings.bucket_name)
        if stats:
            BUCKET_USAGE_BYTES.labels(bucket_name=settings.bucket_name).set(stats["total_size_bytes"])
            BUCKET_OBJECTS.labels(bucket_name=settings.bucket_name).set(stats["total_objects"])
    except Exception as e:
        print(f"Error updating metrics: {e}")

if __name__ == "__main__":
    start_http_server(settings.metrics_port)
    print(f"Prometheus metrics server started on port {settings.metrics_port}")

    scheduler = AsyncIOScheduler()
    scheduler.add_job(update_metrics, 'interval', seconds=60)
    scheduler.start()

    # Keep the script running
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
