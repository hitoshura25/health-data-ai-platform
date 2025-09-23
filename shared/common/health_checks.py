"""
Health check utilities for Health Data AI Platform services.
"""

import asyncio
import psycopg2
import redis
import aio_pika
from minio import Minio
from typing import Dict, Any, Optional, List
import structlog
from datetime import datetime
import traceback
from dataclasses import dataclass
from enum import Enum


class HealthStatus(Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    service: str
    status: HealthStatus
    message: str
    duration_ms: float
    timestamp: str
    details: Optional[Dict[str, Any]] = None


class HealthChecker:
    """Comprehensive health checking for platform services."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize health checker with configuration.

        Args:
            config: Configuration dictionary with connection details
        """
        self.config = config
        self.logger = structlog.get_logger(__name__)

    async def check_all(self) -> Dict[str, HealthCheckResult]:
        """
        Run all configured health checks.

        Returns:
            Dictionary of health check results by service name
        """
        checks = []
        results = {}

        # Database check
        if "database_url" in self.config:
            checks.append(self._check_database())

        # Redis check
        if "redis_url" in self.config:
            checks.append(self._check_redis())

        # RabbitMQ check
        if "rabbitmq_url" in self.config:
            checks.append(self._check_rabbitmq())

        # MinIO check
        if "minio_endpoint" in self.config:
            checks.append(self._check_minio())

        # MLflow check
        if "mlflow_tracking_uri" in self.config:
            checks.append(self._check_mlflow())

        # Execute all checks concurrently
        if checks:
            check_results = await asyncio.gather(*checks, return_exceptions=True)

            for result in check_results:
                if isinstance(result, HealthCheckResult):
                    results[result.service] = result
                elif isinstance(result, Exception):
                    self.logger.error("Health check failed with exception", error=str(result))

        return results

    async def _check_database(self) -> HealthCheckResult:
        """Check PostgreSQL database connectivity."""
        start_time = datetime.utcnow()
        service = "database"

        try:
            # Use psycopg2 for simple connection test
            conn = psycopg2.connect(self.config["database_url"])

            # Simple query to verify functionality
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()

            conn.close()

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            if result and result[0] == 1:
                return HealthCheckResult(
                    service=service,
                    status=HealthStatus.HEALTHY,
                    message="Database connection successful",
                    duration_ms=duration_ms,
                    timestamp=datetime.utcnow().isoformat(),
                    details={"query_result": result[0]}
                )
            else:
                return HealthCheckResult(
                    service=service,
                    status=HealthStatus.DEGRADED,
                    message="Database query returned unexpected result",
                    duration_ms=duration_ms,
                    timestamp=datetime.utcnow().isoformat()
                )

        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return HealthCheckResult(
                service=service,
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {str(e)}",
                duration_ms=duration_ms,
                timestamp=datetime.utcnow().isoformat(),
                details={"error": str(e), "traceback": traceback.format_exc()}
            )

    async def _check_redis(self) -> HealthCheckResult:
        """Check Redis connectivity."""
        start_time = datetime.utcnow()
        service = "redis"

        try:
            r = redis.from_url(self.config["redis_url"])

            # Test basic operations
            test_key = "health_check_test"
            test_value = "health_check_value"

            r.set(test_key, test_value, ex=60)  # Expire in 60 seconds
            retrieved_value = r.get(test_key)
            r.delete(test_key)

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            if retrieved_value and retrieved_value.decode() == test_value:
                # Get Redis info
                info = r.info()
                return HealthCheckResult(
                    service=service,
                    status=HealthStatus.HEALTHY,
                    message="Redis connection and operations successful",
                    duration_ms=duration_ms,
                    timestamp=datetime.utcnow().isoformat(),
                    details={
                        "redis_version": info.get("redis_version"),
                        "used_memory_human": info.get("used_memory_human"),
                        "connected_clients": info.get("connected_clients")
                    }
                )
            else:
                return HealthCheckResult(
                    service=service,
                    status=HealthStatus.DEGRADED,
                    message="Redis operations failed",
                    duration_ms=duration_ms,
                    timestamp=datetime.utcnow().isoformat()
                )

        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return HealthCheckResult(
                service=service,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection failed: {str(e)}",
                duration_ms=duration_ms,
                timestamp=datetime.utcnow().isoformat(),
                details={"error": str(e)}
            )

    async def _check_rabbitmq(self) -> HealthCheckResult:
        """Check RabbitMQ connectivity."""
        start_time = datetime.utcnow()
        service = "rabbitmq"

        try:
            connection = await aio_pika.connect_robust(self.config["rabbitmq_url"])

            # Test channel creation
            channel = await connection.channel()

            # Declare a test queue (won't create if exists)
            test_queue = await channel.declare_queue(
                "health_check_test",
                durable=False,
                auto_delete=True
            )

            # Clean up
            await test_queue.delete()
            await connection.close()

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            return HealthCheckResult(
                service=service,
                status=HealthStatus.HEALTHY,
                message="RabbitMQ connection and operations successful",
                duration_ms=duration_ms,
                timestamp=datetime.utcnow().isoformat()
            )

        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return HealthCheckResult(
                service=service,
                status=HealthStatus.UNHEALTHY,
                message=f"RabbitMQ connection failed: {str(e)}",
                duration_ms=duration_ms,
                timestamp=datetime.utcnow().isoformat(),
                details={"error": str(e)}
            )

    async def _check_minio(self) -> HealthCheckResult:
        """Check MinIO/S3 connectivity."""
        start_time = datetime.utcnow()
        service = "minio"

        try:
            client = Minio(
                self.config["minio_endpoint"],
                access_key=self.config.get("minio_access_key", ""),
                secret_key=self.config.get("minio_secret_key", ""),
                secure=self.config.get("minio_secure", False)
            )

            # Test bucket listing
            buckets = list(client.list_buckets())

            # Test bucket existence for configured bucket
            bucket_name = self.config.get("minio_bucket", "health-data")
            bucket_exists = client.bucket_exists(bucket_name)

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            return HealthCheckResult(
                service=service,
                status=HealthStatus.HEALTHY if bucket_exists else HealthStatus.DEGRADED,
                message=f"MinIO connection successful. Bucket '{bucket_name}' {'exists' if bucket_exists else 'missing'}",
                duration_ms=duration_ms,
                timestamp=datetime.utcnow().isoformat(),
                details={
                    "bucket_count": len(buckets),
                    "target_bucket_exists": bucket_exists,
                    "target_bucket": bucket_name
                }
            )

        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return HealthCheckResult(
                service=service,
                status=HealthStatus.UNHEALTHY,
                message=f"MinIO connection failed: {str(e)}",
                duration_ms=duration_ms,
                timestamp=datetime.utcnow().isoformat(),
                details={"error": str(e)}
            )

    async def _check_mlflow(self) -> HealthCheckResult:
        """Check MLflow tracking server connectivity."""
        start_time = datetime.utcnow()
        service = "mlflow"

        try:
            import httpx

            # Simple HTTP check to MLflow API
            mlflow_url = self.config["mlflow_tracking_uri"]
            health_url = f"{mlflow_url}/health"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(health_url)

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            if response.status_code == 200:
                return HealthCheckResult(
                    service=service,
                    status=HealthStatus.HEALTHY,
                    message="MLflow tracking server is accessible",
                    duration_ms=duration_ms,
                    timestamp=datetime.utcnow().isoformat(),
                    details={"status_code": response.status_code}
                )
            else:
                return HealthCheckResult(
                    service=service,
                    status=HealthStatus.DEGRADED,
                    message=f"MLflow tracking server returned status {response.status_code}",
                    duration_ms=duration_ms,
                    timestamp=datetime.utcnow().isoformat(),
                    details={"status_code": response.status_code}
                )

        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return HealthCheckResult(
                service=service,
                status=HealthStatus.UNHEALTHY,
                message=f"MLflow connection failed: {str(e)}",
                duration_ms=duration_ms,
                timestamp=datetime.utcnow().isoformat(),
                details={"error": str(e)}
            )

    def get_overall_status(self, results: Dict[str, HealthCheckResult]) -> HealthStatus:
        """
        Determine overall system health from individual check results.

        Args:
            results: Dictionary of health check results

        Returns:
            Overall system health status
        """
        if not results:
            return HealthStatus.UNHEALTHY

        unhealthy_count = sum(1 for result in results.values() if result.status == HealthStatus.UNHEALTHY)
        degraded_count = sum(1 for result in results.values() if result.status == HealthStatus.DEGRADED)

        if unhealthy_count > 0:
            return HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def format_health_response(self, results: Dict[str, HealthCheckResult]) -> Dict[str, Any]:
        """
        Format health check results for API response.

        Args:
            results: Dictionary of health check results

        Returns:
            Formatted health response
        """
        overall_status = self.get_overall_status(results)

        return {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                service: {
                    "status": result.status.value,
                    "message": result.message,
                    "duration_ms": result.duration_ms,
                    "details": result.details
                }
                for service, result in results.items()
            },
            "summary": {
                "total_services": len(results),
                "healthy": sum(1 for r in results.values() if r.status == HealthStatus.HEALTHY),
                "degraded": sum(1 for r in results.values() if r.status == HealthStatus.DEGRADED),
                "unhealthy": sum(1 for r in results.values() if r.status == HealthStatus.UNHEALTHY)
            }
        }