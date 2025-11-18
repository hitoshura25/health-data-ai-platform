"""
Metrics and health check server for ETL Narrative Engine.

Provides HTTP endpoints for Prometheus metrics and health checks.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog
import uvicorn
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from ..config.settings import settings
from . import metrics

logger = structlog.get_logger()


class MetricsServer:
    """HTTP server for metrics and health endpoints"""

    def __init__(self):
        self.app = FastAPI(
            title="ETL Narrative Engine Metrics",
            description="Prometheus metrics and health check endpoints",
            version=settings.version
        )
        self.server: uvicorn.Server | None = None
        self.server_task: asyncio.Task | None = None
        self.start_time = datetime.now(UTC)

        # Health check dependencies status
        self.rabbitmq_healthy = False
        self.s3_healthy = False

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup HTTP routes"""

        @self.app.get("/health", response_class=JSONResponse)
        async def health_check() -> dict[str, Any]:
            """Health check endpoint"""
            is_healthy = self.rabbitmq_healthy and self.s3_healthy
            uptime_seconds = (datetime.now(UTC) - self.start_time).total_seconds()

            return {
                "status": "healthy" if is_healthy else "degraded",
                "service": settings.service_name,
                "version": settings.version,
                "environment": settings.environment,
                "uptime_seconds": uptime_seconds,
                "dependencies": {
                    "rabbitmq": "connected" if self.rabbitmq_healthy else "disconnected",
                    "s3": "connected" if self.s3_healthy else "disconnected"
                },
                "timestamp": datetime.now(UTC).isoformat()
            }

        @self.app.get("/metrics", response_class=PlainTextResponse)
        async def prometheus_metrics() -> Response:
            """Prometheus metrics endpoint"""
            metrics_output = generate_latest()
            return Response(
                content=metrics_output,
                media_type=CONTENT_TYPE_LATEST
            )

        @self.app.get("/ready", response_class=JSONResponse)
        async def readiness_check() -> dict[str, Any]:
            """Readiness check for Kubernetes"""
            is_ready = self.rabbitmq_healthy and self.s3_healthy

            return {
                "ready": is_ready,
                "checks": {
                    "rabbitmq": self.rabbitmq_healthy,
                    "s3": self.s3_healthy
                }
            }

        @self.app.get("/live", response_class=JSONResponse)
        async def liveness_check() -> dict[str, Any]:
            """Liveness check for Kubernetes"""
            return {
                "alive": True,
                "timestamp": datetime.now(UTC).isoformat()
            }

    def update_rabbitmq_status(self, healthy: bool):
        """Update RabbitMQ health status"""
        self.rabbitmq_healthy = healthy
        metrics.set_rabbitmq_status(healthy)

    def update_s3_status(self, healthy: bool):
        """Update S3 health status"""
        self.s3_healthy = healthy
        metrics.set_s3_status(healthy)

    async def start(self):
        """Start the metrics server"""
        if not settings.enable_metrics:
            logger.info("metrics_server_disabled")
            return

        logger.info(
            "starting_metrics_server",
            port=settings.metrics_port
        )

        config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=settings.metrics_port,
            log_level=settings.log_level.lower(),
            access_log=False
        )

        self.server = uvicorn.Server(config)
        self.server_task = asyncio.create_task(self.server.serve())

        logger.info(
            "metrics_server_started",
            port=settings.metrics_port,
            endpoints=["/health", "/metrics", "/ready", "/live"]
        )

    async def stop(self):
        """Stop the metrics server"""
        if self.server:
            logger.info("stopping_metrics_server")
            self.server.should_exit = True

            if self.server_task:
                try:
                    await asyncio.wait_for(self.server_task, timeout=5.0)
                except TimeoutError:
                    logger.warning("metrics_server_stop_timeout")
                    self.server_task.cancel()

            logger.info("metrics_server_stopped")
