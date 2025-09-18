# kafka_queue.py
import os
import json
import logging
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import asyncio

logger = logging.getLogger(__name__)

class KafkaQueue:
    def __init__(self, topic=None, bootstrap_servers=None, group_id=None, response_topic=None):
        self.topic = topic or os.getenv("KAFKA_TOPIC", "inferno-queue")
        self.response_topic = response_topic or os.getenv("KAFKA_RESPONSE_TOPIC", "inferno-response-queue")
        self.bootstrap_servers = bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        self.group_id = group_id or os.getenv("KAFKA_GROUP_ID", "inferno-consumer-group")
        self.producer = None
        self.consumer = None
        # The response consumer is removed from here and will be managed by the dispatcher in main.py

    async def start_producer(self):
        try:
            self.producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
            await self.producer.start()
            logger.info(f"[KafkaQueue] Producer started for topic {self.topic} at {self.bootstrap_servers}")
        except Exception as e:
            logger.error(f"[KafkaQueue] Failed to start producer: {e}", exc_info=True)
            raise

    async def stop_producer(self):
        if self.producer:
            await self.producer.stop()
            logger.info("[KafkaQueue] Producer stopped")

    async def push_to_queue(self, message: dict, topic: str = None):
    # The check `self.producer.is_closed()` was incorrect and has been removed.
        if not self.producer:
            await self.start_producer()
        try:
            target_topic = topic or self.topic
            await self.producer.send_and_wait(target_topic, json.dumps(message).encode("utf-8"))
            logger.info(f"[KafkaQueue] Pushed message to Kafka topic '{target_topic}': {message}")
            return True
        except Exception as e:
            logger.error(f"[KafkaQueue] Error pushing to Kafka topic: {e}", exc_info=True)
            return False

    async def start_consumer(self, topic: str = None):
        try:
            self.consumer = AIOKafkaConsumer(
                topic or self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                enable_auto_commit=True,
                auto_offset_reset="earliest"
            )
            await self.consumer.start()
            logger.info(f"[KafkaQueue] Consumer started for topic {topic or self.topic} at {self.bootstrap_servers}")
        except Exception as e:
            logger.error(f"[KafkaQueue] Failed to start consumer for topic {topic or self.topic}: {e}", exc_info=True)
            raise

    async def stop_consumer(self):
        if self.consumer:
            await self.consumer.stop()
            logger.info("[KafkaQueue] Consumer stopped")

    async def consume(self):
        """Yields messages from the configured topic."""
        if not self.consumer:
            await self.start_consumer()
        try:
            async for msg in self.consumer:
                try:
                    logger.info(f"[KafkaQueue] Consumed message from Kafka: {msg.value}")
                    yield json.loads(msg.value.decode("utf-8"))
                except json.JSONDecodeError as e:
                    logger.error(f"[KafkaQueue] Error decoding Kafka message: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"[KafkaQueue] Error consuming from Kafka: {e}", exc_info=True)

    @staticmethod
    async def health_check():
        # This implementation is fine as it creates a short-lived producer for a quick check.
        try:
            producer = AIOKafkaProducer(bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"))
            await producer.start()
            await producer.stop()
            return True
        except Exception as e:
            logger.error(f"[KafkaQueue] Kafka health check failed: {e}", exc_info=True)
            return False