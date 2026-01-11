import os
import json
import asyncio
import aio_pika
from loguru import logger
from langchain_core.messages import HumanMessage
from src.graph import graph
from src.producer import producer

class RabbitMQConsumer:
    def __init__(self):
        self.user = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
        self.password = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")
        self.host = os.getenv("RABBITMQ_HOST", "rabbitmq")
        self.port = int(os.getenv("RABBITMQ_PORT", 5672))
        self.connection = None
        self.channel = None

    async def connect(self):
        url = f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/"
        try:
            self.connection = await aio_pika.connect_robust(url)
            self.channel = await self.connection.channel()
            # QoS
            await self.channel.set_qos(prefetch_count=10)
            logger.info("Connected to RabbitMQ Consumer")
        except Exception as e:
            logger.error(f"Consumer connection failed: {e}")
            raise

    async def process_message(self, message: aio_pika.IncomingMessage):
        async with message.process():
            try:
                data = json.loads(message.body.decode())
                logger.info(f"Received event: {data}")
                
                user_id = data.get("user_id")
                chat_id = data.get("chat_id")
                text = data.get("text")
                file_path = data.get("file_path")
                
                # Check for content (text or file)
                if not text and not file_path:
                    logger.warning("Empty content in message")
                    return

                # Save User Message to Memory
                # Note: We currently only save text to memory history. 
                # Files are transient for the current turn.
                if chat_id:
                    from src.utils import save_message
                    content_to_save = text
                    if file_path:
                        content_to_save += f" [File: {file_path}]"
                    await save_message(chat_id=chat_id, role="user", content=content_to_save)

                # Invoke Graph
                # Pass chat_id to state
                input_state = {
                    "messages": [HumanMessage(content=text or "")],
                    "chat_id": chat_id,
                    "files": [file_path] if file_path else []
                }
                
                result = await graph.ainvoke(input_state)
                
                # Get last message
                last_message = result["messages"][-1]
                response_text = last_message.content
                
                # Send back to Gateway
                if chat_id:
                    await producer.send_response(chat_id, response_text)
                
            except Exception as e:
                logger.exception(f"Error processing message: {e}")

    async def start(self):
        if not self.channel:
            raise RuntimeError("Consumer not connected")
            
        queue = await self.channel.declare_queue("chat_events", durable=True)
        await queue.consume(self.process_message)
        logger.info("Started consuming chat_events")

    async def close(self):
        if self.connection:
            await self.connection.close()
            
consumer = RabbitMQConsumer()
