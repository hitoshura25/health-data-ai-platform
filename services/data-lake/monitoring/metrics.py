from prometheus_client import Gauge, Counter, Histogram

# Bucket Metrics
BUCKET_USAGE_BYTES = Gauge(
    "minio_bucket_usage_total_bytes",
    "Total size of the bucket in bytes",
    ["bucket_name"],
)

BUCKET_OBJECTS = Gauge(
    "minio_bucket_objects_total",
    "Total number of objects in the bucket",
    ["bucket_name"],
)

# HTTP Metrics
HTTP_REQUESTS_TOTAL = Counter(
    "minio_http_requests_total",
    "Total number of HTTP requests to MinIO",
    ["bucket_name", "method", "status_code"],
)

HTTP_REQUESTS_DURATION_SECONDS = Histogram(
    "minio_http_requests_duration_seconds",
    "Histogram of HTTP request durations in seconds",
    ["bucket_name", "method"],
)
