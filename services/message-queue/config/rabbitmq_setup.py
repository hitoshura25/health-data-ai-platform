import aio_pika
import asyncio
import sys
import os

# Add the service directory to the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.settings import settings
import structlog

logger = structlog.get_logger()

async def setup_rabbitmq_infrastructure():
    """Set up RabbitMQ exchanges and queues"""
    try:
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    except Exception as e:
        logger.error("Failed to connect to RabbitMQ", error=e)
        sys.exit(1)

    async with connection:
        channel = await connection.channel()

        try:
            # Declare exchanges
            main_exchange = await channel.declare_exchange(
                settings.main_exchange,
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            logger.info("Exchange declared", exchange=settings.main_exchange)

            dlx_exchange = await channel.declare_exchange(
                settings.dlx_exchange,
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            logger.info("Exchange declared", exchange=settings.dlx_exchange)

            # Declare main processing queue
            processing_queue = await channel.declare_queue(
                settings.processing_queue,
                durable=True,
                arguments={
                    "x-message-ttl": settings.message_ttl_seconds * 1000,
                    "x-dead-letter-exchange": settings.dlx_exchange,
                    "x-dead-letter-routing-key": "failed.processing"
                }
            )
            logger.info("Queue declared", queue=settings.processing_queue)

            # Bind processing queue
            await processing_queue.bind(main_exchange, "health.processing.#")
            logger.info("Queue bound", queue=settings.processing_queue, exchange=settings.main_exchange)

            # Declare failed queue
            failed_queue = await channel.declare_queue(
                settings.failed_queue,
                durable=True
            )
            logger.info("Queue declared", queue=settings.failed_queue)

            # Bind failed queue
            await failed_queue.bind(dlx_exchange, "failed.#")
            logger.info("Queue bound", queue=settings.failed_queue, exchange=settings.dlx_exchange)

            # Create retry queues
            for delay in settings.retry_delays:
                retry_queue_name = f"health_data_retry_{delay}s"
                await channel.declare_queue(
                    retry_queue_name,
                    durable=True,
                    arguments={
                        "x-message-ttl": delay * 1000,
                        "x-dead-letter-exchange": settings.main_exchange,
                        # This routing key sends it back to the main processing queue
                        "x-dead-letter-routing-key": "health.processing.retry"
                    }
                )
                logger.info("Retry queue declared", queue=retry_queue_name, delay=f"{delay}s")

            logger.info("RabbitMQ infrastructure setup completed successfully")

        except Exception as e:
            logger.error("Failed to setup RabbitMQ infrastructure", error=e)
            sys.exit(1)

if __name__ == "__main__":
    # This is to fix the same import issue as in the tests
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from config.settings import settings
    
    # A simple logger for script execution
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )
    asyncio.run(setup_rabbitmq_infrastructure())
