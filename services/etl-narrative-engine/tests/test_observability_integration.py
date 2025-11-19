"""
Integration tests for observability features.

Tests metrics server, health checks, and distributed tracing integration.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.monitoring import MetricsServer, initialize_metrics
from src.monitoring.metrics import (
    record_message_processed,
    record_processing_time,
    record_quality_score,
    record_validation_check,
    set_consumer_status,
    set_rabbitmq_status,
    set_s3_status,
)


class TestMetricsServer:
    """Test metrics server HTTP endpoints"""

    def setup_method(self):
        """Setup test fixtures"""
        self.metrics_server = MetricsServer()
        self.client = TestClient(self.metrics_server.app)

    def test_health_endpoint_healthy(self):
        """Test /health endpoint when all dependencies are healthy"""
        # Setup
        self.metrics_server.update_rabbitmq_status(True)
        self.metrics_server.update_s3_status(True)

        # Execute
        response = self.client.get("/health")

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["dependencies"]["rabbitmq"] == "connected"
        assert data["dependencies"]["s3"] == "connected"
        assert "uptime_seconds" in data
        assert "timestamp" in data

    def test_health_endpoint_degraded(self):
        """Test /health endpoint when dependencies are unhealthy"""
        # Setup
        self.metrics_server.update_rabbitmq_status(False)
        self.metrics_server.update_s3_status(False)

        # Execute
        response = self.client.get("/health")

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["dependencies"]["rabbitmq"] == "disconnected"
        assert data["dependencies"]["s3"] == "disconnected"

    def test_health_endpoint_partial_degradation(self):
        """Test /health endpoint with partial degradation"""
        # Setup
        self.metrics_server.update_rabbitmq_status(True)
        self.metrics_server.update_s3_status(False)

        # Execute
        response = self.client.get("/health")

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["dependencies"]["rabbitmq"] == "connected"
        assert data["dependencies"]["s3"] == "disconnected"

    def test_metrics_endpoint(self):
        """Test /metrics endpoint returns Prometheus format"""
        # Setup - record some test metrics
        record_message_processed("BloodGlucoseRecord", "success")
        record_processing_time("BloodGlucoseRecord", 2.5)

        # Execute
        response = self.client.get("/metrics")

        # Verify
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

        content = response.text
        assert "etl_messages_processed_total" in content
        assert "etl_processing_duration_seconds" in content

    def test_ready_endpoint_ready(self):
        """Test /ready endpoint when service is ready"""
        # Setup
        self.metrics_server.update_rabbitmq_status(True)
        self.metrics_server.update_s3_status(True)

        # Execute
        response = self.client.get("/ready")

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True
        assert data["checks"]["rabbitmq"] is True
        assert data["checks"]["s3"] is True

    def test_ready_endpoint_not_ready(self):
        """Test /ready endpoint when service is not ready"""
        # Setup
        self.metrics_server.update_rabbitmq_status(False)
        self.metrics_server.update_s3_status(True)

        # Execute
        response = self.client.get("/ready")

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is False
        assert data["checks"]["rabbitmq"] is False

    def test_live_endpoint(self):
        """Test /live endpoint always returns alive"""
        # Execute
        response = self.client.get("/live")

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["alive"] is True
        assert "timestamp" in data


class TestMetricsCollection:
    """Test metrics collection functionality"""

    def test_record_message_processed(self):
        """Test recording processed messages"""
        # Execute
        record_message_processed("BloodGlucoseRecord", "success")
        record_message_processed("HeartRateRecord", "failed")
        record_message_processed("BloodGlucoseRecord", "success")

        # Verify - no exceptions raised
        # Actual metric values tested via metrics endpoint

    def test_record_processing_time(self):
        """Test recording processing duration"""
        # Execute
        record_processing_time("BloodGlucoseRecord", 2.5)
        record_processing_time("HeartRateRecord", 1.2)
        record_processing_time("SleepSessionRecord", 5.8)

        # Verify - no exceptions raised

    def test_record_validation_metrics(self):
        """Test recording validation metrics"""
        # Execute
        record_validation_check("BloodGlucoseRecord", "completeness", "passed")
        record_validation_check("HeartRateRecord", "consistency", "failed")
        record_quality_score("BloodGlucoseRecord", 0.95)
        record_quality_score("HeartRateRecord", 0.65)

        # Verify - no exceptions raised

    def test_set_system_status(self):
        """Test setting system status metrics"""
        # Execute
        set_consumer_status(True)
        set_rabbitmq_status(True)
        set_s3_status(True)

        set_consumer_status(False)

        # Verify - no exceptions raised


@pytest.mark.integration
class TestObservabilityIntegration:
    """Integration tests for full observability stack"""

    @pytest.mark.asyncio
    async def test_metrics_server_lifecycle(self):
        """Test metrics server start and stop"""
        # Setup
        with patch('src.monitoring.server.settings') as mock_settings:
            mock_settings.enable_metrics = True
            mock_settings.metrics_port = 18004  # Use different port for testing
            mock_settings.log_level = "INFO"

            metrics_server = MetricsServer()

            # Execute - start server
            await metrics_server.start()

            # Verify server is running
            assert metrics_server.server is not None
            assert metrics_server.server_task is not None

            # Stop server
            await metrics_server.stop()

    @pytest.mark.asyncio
    async def test_metrics_server_disabled(self):
        """Test metrics server when disabled in config"""
        # Setup
        with patch('src.monitoring.server.settings') as mock_settings:
            mock_settings.enable_metrics = False

            metrics_server = MetricsServer()

            # Execute
            await metrics_server.start()

            # Verify - server should not start
            assert metrics_server.server is None

    def test_initialize_metrics(self):
        """Test metrics initialization"""
        # Execute
        initialize_metrics(
            service_name="test-service",
            version="1.0.0",
            environment="test"
        )

        # Verify - no exceptions raised
        # Initial metrics should be set


@pytest.mark.integration
class TestMetricsEndToEnd:
    """End-to-end tests for metrics collection and export"""

    def setup_method(self):
        """Setup test fixtures"""
        self.metrics_server = MetricsServer()
        self.client = TestClient(self.metrics_server.app)

    def test_end_to_end_message_processing_metrics(self):
        """Test complete message processing metrics flow"""
        # Simulate message processing workflow
        record_message_processed("BloodGlucoseRecord", "success")
        record_processing_time("BloodGlucoseRecord", 3.2)
        record_validation_check("BloodGlucoseRecord", "completeness", "passed")
        record_quality_score("BloodGlucoseRecord", 0.92)

        # Verify metrics are exported
        response = self.client.get("/metrics")
        assert response.status_code == 200

        content = response.text
        assert "BloodGlucoseRecord" in content
        assert "success" in content

    def test_end_to_end_system_health(self):
        """Test complete system health check flow"""
        # Simulate system status updates
        self.metrics_server.update_rabbitmq_status(True)
        self.metrics_server.update_s3_status(True)
        set_consumer_status(True)

        # Verify health endpoint
        response = self.client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["dependencies"]["rabbitmq"] == "connected"
        assert data["dependencies"]["s3"] == "connected"

    def test_metrics_cardinality(self):
        """Test metrics with different label combinations"""
        # Record metrics with various labels
        record_types = ["BloodGlucoseRecord", "HeartRateRecord", "SleepSessionRecord"]
        statuses = ["success", "failed", "quarantined"]

        for record_type in record_types:
            for status in statuses:
                record_message_processed(record_type, status)

        # Verify all metrics are exported
        response = self.client.get("/metrics")
        assert response.status_code == 200

        content = response.text
        for record_type in record_types:
            assert record_type in content


class TestHealthCheckIntegration:
    """Test health check integration with dependencies"""

    def setup_method(self):
        """Setup test fixtures"""
        self.metrics_server = MetricsServer()
        self.client = TestClient(self.metrics_server.app)

    def test_health_check_status_transitions(self):
        """Test health status transitions"""
        # Start healthy
        self.metrics_server.update_rabbitmq_status(True)
        self.metrics_server.update_s3_status(True)

        response = self.client.get("/health")
        assert response.json()["status"] == "healthy"

        # Degrade RabbitMQ
        self.metrics_server.update_rabbitmq_status(False)

        response = self.client.get("/health")
        assert response.json()["status"] == "degraded"

        # Recover RabbitMQ
        self.metrics_server.update_rabbitmq_status(True)

        response = self.client.get("/health")
        assert response.json()["status"] == "healthy"

    def test_readiness_vs_liveness(self):
        """Test difference between readiness and liveness"""
        # Setup - dependencies not ready
        self.metrics_server.update_rabbitmq_status(False)
        self.metrics_server.update_s3_status(False)

        # Liveness should always pass
        liveness_response = self.client.get("/live")
        assert liveness_response.status_code == 200
        assert liveness_response.json()["alive"] is True

        # Readiness should fail
        readiness_response = self.client.get("/ready")
        assert readiness_response.status_code == 200
        assert readiness_response.json()["ready"] is False
