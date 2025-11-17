"""
Main entry point for ETL Narrative Engine.

Starts the consumer and handles graceful shutdown.
"""

import asyncio
import signal
import structlog
from .consumer.etl_consumer import ETLConsumer
from .config.settings import settings

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

    # Create consumer
    consumer = ETLConsumer()

    # Initialize consumer
    await consumer.initialize()

    # Handle shutdown signals
    def signal_handler():
        logger.info("shutdown_signal_received")
        asyncio.create_task(consumer.stop())

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        # Start consuming
        await consumer.start_consuming()

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
