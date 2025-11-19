"""
Unit tests for distributed tracing module.

Tests OpenTelemetry integration, span creation, and attribute management.
"""

from unittest.mock import Mock, patch

import pytest

from src.monitoring.tracing import (
    TracingContext,
    add_span_attributes,
    create_span,
    get_tracer,
    record_exception,
    setup_tracing,
    trace_async_function,
)


class TestTracingSetup:
    """Test tracing initialization and configuration"""

    @patch('src.monitoring.tracing.settings')
    @patch('src.monitoring.tracing.OTLPSpanExporter')
    @patch('src.monitoring.tracing.TracerProvider')
    def test_setup_tracing_enabled(self, mock_provider_class, mock_exporter_class, mock_settings):
        """Test tracing setup when enabled"""
        # Setup
        mock_settings.enable_jaeger_tracing = True
        mock_settings.jaeger_service_name = "test-service"
        mock_settings.jaeger_otlp_endpoint = "http://localhost:4319"
        mock_settings.version = "1.0.0"
        mock_settings.environment = "test"

        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_exporter = Mock()
        mock_exporter_class.return_value = mock_exporter

        # Execute
        tracer = setup_tracing()

        # Verify
        assert tracer is not None
        mock_provider_class.assert_called_once()
        mock_exporter_class.assert_called_once_with(
            endpoint="http://localhost:4319",
            insecure=True
        )
        mock_provider.add_span_processor.assert_called_once()

    @patch('src.monitoring.tracing.settings')
    def test_setup_tracing_disabled(self, mock_settings):
        """Test tracing setup when disabled"""
        # Setup
        mock_settings.enable_jaeger_tracing = False

        # Execute
        tracer = setup_tracing()

        # Verify - should return a tracer (no-op)
        assert tracer is not None

    @patch('src.monitoring.tracing.settings')
    @patch('src.monitoring.tracing.OTLPSpanExporter')
    def test_setup_tracing_error_handling(self, mock_exporter_class, mock_settings):
        """Test tracing setup handles errors gracefully"""
        # Setup
        mock_settings.enable_jaeger_tracing = True
        mock_settings.jaeger_service_name = "test-service"
        mock_settings.jaeger_otlp_endpoint = "http://localhost:4319"
        mock_settings.version = "1.0.0"
        mock_settings.environment = "test"
        mock_exporter_class.side_effect = Exception("Connection failed")

        # Execute - should not raise, returns no-op tracer
        tracer = setup_tracing()

        # Verify
        assert tracer is not None

    def test_get_tracer_returns_instance(self):
        """Test get_tracer returns a tracer instance"""
        # Execute
        tracer = get_tracer()

        # Verify
        assert tracer is not None


class TestTraceAsyncFunction:
    """Test async function tracing decorator"""

    @pytest.mark.asyncio
    @patch('src.monitoring.tracing.settings')
    async def test_trace_async_function_success(self, mock_settings):
        """Test tracing decorator on successful function"""
        # Setup
        mock_settings.enable_jaeger_tracing = False  # Use no-op tracer for testing

        @trace_async_function("test_operation")
        async def sample_function(x, y):
            return x + y

        # Execute
        result = await sample_function(2, 3)

        # Verify
        assert result == 5

    @pytest.mark.asyncio
    @patch('src.monitoring.tracing.settings')
    async def test_trace_async_function_with_exception(self, mock_settings):
        """Test tracing decorator records exceptions"""
        # Setup
        mock_settings.enable_jaeger_tracing = False

        @trace_async_function("test_operation")
        async def failing_function():
            raise ValueError("Test error")

        # Execute & Verify
        with pytest.raises(ValueError, match="Test error"):
            await failing_function()

    @pytest.mark.asyncio
    @patch('src.monitoring.tracing.settings')
    async def test_trace_async_function_with_custom_attributes(self, mock_settings):
        """Test tracing decorator with custom attributes"""
        # Setup
        mock_settings.enable_jaeger_tracing = False

        @trace_async_function("test_operation", attributes={"custom_key": "custom_value"})
        async def sample_function():
            return "success"

        # Execute
        result = await sample_function()

        # Verify
        assert result == "success"

    @pytest.mark.asyncio
    @patch('src.monitoring.tracing.settings')
    async def test_trace_async_function_disabled(self, mock_settings):
        """Test tracing decorator when tracing is disabled"""
        # Setup
        mock_settings.enable_jaeger_tracing = False

        call_count = 0

        @trace_async_function("test_operation")
        async def sample_function():
            nonlocal call_count
            call_count += 1
            return "success"

        # Execute
        result = await sample_function()

        # Verify - function still executes normally
        assert result == "success"
        assert call_count == 1


class TestSpanAttributes:
    """Test span attribute management"""

    @patch('src.monitoring.tracing.settings')
    @patch('src.monitoring.tracing.trace.get_current_span')
    def test_add_span_attributes_enabled(self, mock_get_span, mock_settings):
        """Test adding attributes to current span"""
        # Setup
        mock_settings.enable_jaeger_tracing = True
        mock_span = Mock()
        mock_span.is_recording.return_value = True
        mock_get_span.return_value = mock_span

        attributes = {
            "string_attr": "value",
            "int_attr": 123,
            "float_attr": 3.14,
            "bool_attr": True
        }

        # Execute
        add_span_attributes(attributes)

        # Verify
        assert mock_span.set_attribute.call_count == 4
        mock_span.set_attribute.assert_any_call("string_attr", "value")
        mock_span.set_attribute.assert_any_call("int_attr", 123)
        mock_span.set_attribute.assert_any_call("float_attr", 3.14)
        mock_span.set_attribute.assert_any_call("bool_attr", True)

    @patch('src.monitoring.tracing.settings')
    def test_add_span_attributes_disabled(self, mock_settings):
        """Test adding attributes when tracing disabled"""
        # Setup
        mock_settings.enable_jaeger_tracing = False

        # Execute - should not raise
        add_span_attributes({"key": "value"})

    @patch('src.monitoring.tracing.settings')
    @patch('src.monitoring.tracing.trace.get_current_span')
    def test_add_span_attributes_converts_complex_types(self, mock_get_span, mock_settings):
        """Test that complex types are converted to strings"""
        # Setup
        mock_settings.enable_jaeger_tracing = True
        mock_span = Mock()
        mock_span.is_recording.return_value = True
        mock_get_span.return_value = mock_span

        attributes = {
            "list_attr": [1, 2, 3],
            "dict_attr": {"key": "value"}
        }

        # Execute
        add_span_attributes(attributes)

        # Verify - complex types converted to strings
        assert mock_span.set_attribute.call_count == 2
        mock_span.set_attribute.assert_any_call("list_attr", "[1, 2, 3]")
        mock_span.set_attribute.assert_any_call("dict_attr", "{'key': 'value'}")


class TestRecordException:
    """Test exception recording in spans"""

    @patch('src.monitoring.tracing.settings')
    @patch('src.monitoring.tracing.trace.get_current_span')
    def test_record_exception_enabled(self, mock_get_span, mock_settings):
        """Test recording exception to current span"""
        # Setup
        mock_settings.enable_jaeger_tracing = True
        mock_span = Mock()
        mock_span.is_recording.return_value = True
        mock_get_span.return_value = mock_span

        exception = ValueError("Test error")

        # Execute
        record_exception(exception, {"context": "test"})

        # Verify
        mock_span.record_exception.assert_called_once_with(exception)
        mock_span.set_status.assert_called_once()
        mock_span.set_attribute.assert_called_with("context", "test")

    @patch('src.monitoring.tracing.settings')
    def test_record_exception_disabled(self, mock_settings):
        """Test recording exception when tracing disabled"""
        # Setup
        mock_settings.enable_jaeger_tracing = False
        exception = ValueError("Test error")

        # Execute - should not raise
        record_exception(exception)


class TestTracingContext:
    """Test TracingContext context manager"""

    @patch('src.monitoring.tracing.settings')
    def test_tracing_context_success(self, mock_settings):
        """Test TracingContext with successful operation"""
        # Setup
        mock_settings.enable_jaeger_tracing = False

        # Execute
        with TracingContext("test_span", {"key": "value"}):
            result = 1 + 1

        # Verify
        assert result == 2

    @patch('src.monitoring.tracing.settings')
    def test_tracing_context_with_exception(self, mock_settings):
        """Test TracingContext records exceptions"""
        # Setup
        mock_settings.enable_jaeger_tracing = False

        # Execute & Verify
        with pytest.raises(ValueError, match="Test error"), TracingContext("test_span"):
            raise ValueError("Test error")

    @patch('src.monitoring.tracing.settings')
    def test_tracing_context_disabled(self, mock_settings):
        """Test TracingContext when tracing disabled"""
        # Setup
        mock_settings.enable_jaeger_tracing = False

        # Execute
        with TracingContext("test_span", {"key": "value"}):
            result = "success"

        # Verify - context manager works even when disabled
        assert result == "success"


class TestCreateSpan:
    """Test create_span convenience function"""

    @patch('src.monitoring.tracing.settings')
    def test_create_span(self, mock_settings):
        """Test create_span function"""
        # Setup
        mock_settings.enable_jaeger_tracing = False

        # Execute
        with create_span("test_operation", {"attr": "value"}):
            result = "success"

        # Verify
        assert result == "success"


class TestTracingIntegration:
    """Integration tests for tracing functionality"""

    @pytest.mark.asyncio
    @patch('src.monitoring.tracing.settings')
    async def test_nested_spans(self, mock_settings):
        """Test nested span creation"""
        # Setup
        mock_settings.enable_jaeger_tracing = False

        @trace_async_function("outer_function")
        async def outer():
            with create_span("inner_operation"):
                return "success"

        # Execute
        result = await outer()

        # Verify
        assert result == "success"

    @pytest.mark.asyncio
    @patch('src.monitoring.tracing.settings')
    async def test_tracing_with_multiple_operations(self, mock_settings):
        """Test tracing multiple sequential operations"""
        # Setup
        mock_settings.enable_jaeger_tracing = False

        @trace_async_function("process_data")
        async def process_data():
            with create_span("step_1", {"step": 1}):
                pass

            with create_span("step_2", {"step": 2}):
                pass

            with create_span("step_3", {"step": 3}):
                pass

            return "completed"

        # Execute
        result = await process_data()

        # Verify
        assert result == "completed"
