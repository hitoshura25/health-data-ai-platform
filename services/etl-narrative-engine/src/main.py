"""
Main entry point for ETL Narrative Engine.

Starts the consumer and handles graceful shutdown.
"""

import asyncio
import contextlib
import signal

import structlog

from .config.settings import settings
from .consumer.etl_consumer import ETLConsumer
from .monitoring import MetricsServer, initialize_metrics

logger = structlog.get_logger()


async def main():
    """Main entry point"""

    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer() if settings.log_json else structlog.dev.ConsoleRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logger.info(
        "starting_etl_narrative_engine",
        service=settings.service_name,
        version=settings.version,
        environment=settings.environment
    )

    # Initialize metrics
    initialize_metrics(
        service_name=settings.service_name,
        version=settings.version,
        environment=settings.environment
    )

    # Create metrics server
    metrics_server = MetricsServer()

    # Create consumer
    consumer = ETLConsumer()

    # Initialize consumer
    await consumer.initialize()

    # Start metrics server
    await metrics_server.start()

    # Handle shutdown signals
    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.info("shutdown_signal_received")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        # Start consuming in background
        consumer_task = asyncio.create_task(consumer.start_consuming())

        # Wait for shutdown signal
        await shutdown_event.wait()

        logger.info("initiating_graceful_shutdown")

        # Stop consumer
        await consumer.stop()

        # Cancel consumer task
        if not consumer_task.done():
            consumer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await consumer_task

        # Stop metrics server
        await metrics_server.stop()

    except Exception as e:
        logger.error(
            "fatal_error",
            exception=str(e),
            exception_type=type(e).__name__
        )
        raise

    finally:
        logger.info("etl_narrative_engine_stopped")


if __name__ == "__main__":
    asyncio.run(main())
