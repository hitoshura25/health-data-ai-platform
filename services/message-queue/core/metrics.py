from prometheus_client import Counter, Histogram, Gauge, start_http_server
import structlog

logger = structlog.get_logger()

class MessageQueueMetrics:
    """Comprehensive message queue metrics"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MessageQueueMetrics, cls).__new__(cls)
            cls._instance._initialize_metrics()
        return cls._instance

    def _initialize_metrics(self):
        # Publisher metrics
        self.messages_published = Counter(
            'mq_messages_published_total',
            'Total published messages',
            ['exchange', 'routing_key', 'status']
        )

        self.publish_duration = Histogram(
            'mq_publish_duration_seconds',
            'Message publish duration',
            ['exchange']
        )

        # Consumer metrics
        self.messages_processed = Counter(
            'mq_messages_processed_total',
            'Total processed messages',
            ['queue', 'record_type', 'status']
        )

        self.processing_duration = Histogram(
            'mq_processing_duration_seconds',
            'Message processing duration',
            ['queue', 'record_type']
        )

        # Retry metrics
        self.retry_attempts = Counter(
            'mq_retry_attempts_total',
            'Total retry attempts',
            ['record_type', 'retry_count']
        )

        self.retry_scheduled = Counter(
            'mq_retry_scheduled_total',
            'Total retries scheduled',
            ['record_type', 'delay_seconds']
        )

        # Deduplication metrics
        self.duplicate_messages = Counter(
            'mq_duplicate_messages_total',
            'Duplicate messages detected',
            ['record_type']
        )

        # Failure metrics
        self.permanent_failures = Counter(
            'mq_permanent_failures_total',
            'Permanent message failures',
            ['record_type']
        )

        # System metrics
        self.active_connections = Gauge(
            'mq_active_connections',
            'Number of active connections'
        )

    def record_publish_success(self, exchange: str, routing_key: str, duration: float):
        self.messages_published.labels(exchange=exchange, routing_key=routing_key, status="success").inc()
        self.publish_duration.labels(exchange=exchange).observe(duration)

    def record_publish_failure(self, exchange: str, error_type: str):
        self.messages_published.labels(exchange=exchange, routing_key="unknown", status="failed").inc()

    def record_processing_success(self, queue: str, record_type: str, duration: float):
        self.messages_processed.labels(queue=queue, record_type=record_type, status="success").inc()
        self.processing_duration.labels(queue=queue, record_type=record_type).observe(duration)

    def record_retry_attempt(self, record_type: str, retry_count: int):
        self.retry_attempts.labels(record_type=record_type, retry_count=str(retry_count)).inc()

    def record_retry_scheduled(self, record_type: str, retry_count: int, delay_seconds: int):
        self.retry_scheduled.labels(record_type=record_type, delay_seconds=str(delay_seconds)).inc()

    def record_duplicate_message(self, record_type: str):
        self.duplicate_messages.labels(record_type=record_type).inc()

    def record_permanent_failure(self, record_type: str):
        self.permanent_failures.labels(record_type=record_type).inc()

    def start_metrics_server(self, port: int = 8001):
        """Start Prometheus metrics server"""
        start_http_server(port)
        logger.info("Metrics server started", port=port)
