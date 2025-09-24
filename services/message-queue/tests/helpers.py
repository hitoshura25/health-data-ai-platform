import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.message import HealthDataMessage
from consumer.base_consumer import BaseIdempotentConsumer

class TestConsumer(BaseIdempotentConsumer):
    processed_messages = []

    async def process_health_message(self, message: HealthDataMessage) -> bool:
        self.processed_messages.append(message)
        return True
