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
                
                # Context info
                # "username" in telegram is @handle, which might be None. "first_name" is better for "name".
                # Gateway sends "username" but we might need to check if we can get first_name from gateway event?
                # Let's check bot.py ... event has "username" (from_user.username). 
                # Ideally we want Display Name. 
                # Assuming Gateway sends "username", let's use what we have or update Gateway later.
                # Wait, user request says: "Extract first_name (or username)".
                # I should check what Gateway sends. It sends "username". 
                # I will use "username" for now as "user_name" or "Display Name" if simple.
                # Actually, let's look at `bot.py` again. It sends `username`.
                # If I want `first_name`, I need to update Gateway.
                # But for now let's use `username` as `user_name`.
                user_name = data.get("username") or "User"
                date_str = data.get("date") # ISO format from gateway

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
                    
                    # Save with metadata
                    await save_message(
                        chat_id=chat_id, 
                        role="user", 
                        content=content_to_save,
                        user_name=user_name,
                        created_at=date_str
                    )

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
            
        # Updated to listen to filtered tasks from Initiative Service
        QUEUE_NAME = "brain_tasks"
        queue = await self.channel.declare_queue(QUEUE_NAME, durable=True)
        await queue.consume(self.process_message)
        logger.info(f"Started consuming {QUEUE_NAME}")

    async def close(self):
        if self.connection:
            await self.connection.close()
            
consumer = RabbitMQConsumer()
