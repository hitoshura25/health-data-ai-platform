import sys
import os
import asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.message import HealthDataMessage
from consumer.base_consumer import BaseIdempotentConsumer
import structlog

logger = structlog.get_logger()

class MyConsumer(BaseIdempotentConsumer):
    def __init__(self, *args, stop_after_n_messages=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.processed_messages = []
        self.stop_after_n_messages = stop_after_n_messages
        self._stop_event = None  # Create lazily in the correct event loop

    async def process_health_message(self, message: HealthDataMessage) -> bool:
        self.processed_messages.append(message)
        if self.stop_after_n_messages and len(self.processed_messages) >= self.stop_after_n_messages:
            if self._stop_event:
                self._stop_event.set()
        return True

    async def start_consuming(self):
        """Overrides the base class to implement a graceful stop mechanism."""
        if not self.connection:
            await self.initialize()

        # Create the event in the current event loop
        if self.stop_after_n_messages and not self._stop_event:
            self._stop_event = asyncio.Event()

        self.queue = await self.channel.get_queue(self.queue_name)

        logger.info("Started consuming messages", queue=self.queue_name)
        self._consuming = True
        self._consumer_tag = await self.queue.consume(self._process_message_with_idempotency)

        if self.stop_after_n_messages:
            await self._stop_event.wait()

        await self.stop()
