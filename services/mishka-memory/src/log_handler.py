import sys
import os
import asyncio
import json
import datetime
import aio_pika
from loguru import logger

SERVICE_NAME = os.getenv("SERVICE_NAME", "unknown-service")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

class RabbitMQSink:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.connection = None
        self.channel = None
        self.is_connected = False

    async def start(self):
        try:
            self.connection = await aio_pika.connect_robust(RABBITMQ_URL)
            self.channel = await self.connection.channel()
            await self.channel.declare_queue("system_errors", durable=True)
            self.is_connected = True
            asyncio.create_task(self._process_queue())
            logger.info("Connected to RabbitMQ for error logging.")
        except Exception as e:
            # Fallback to stderr if RMQ fails
            print(f"CRITICAL: Failed to connect logger to RMQ: {e}", file=sys.stderr)

    async def _process_queue(self):
        while True:
            msg = await self.queue.get()
            try:
                if self.channel and self.is_connected:
                    await self.channel.default_exchange.publish(
                        aio_pika.Message(
                            body=json.dumps(msg).encode(),
                            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                        ),
                        routing_key="system_errors"
                    )
            except Exception as e:
                print(f"Failed to log to RMQ: {e}", file=sys.stderr)
            finally:
                self.queue.task_done()
    
    async def stop(self):
        if self.connection:
            await self.connection.close()
            self.is_connected = False

    def sink(self, message):
        record = message.record
        exc = record["exception"]
        
        # Serialize exception if present
        tb = None
        if exc:
            # Simple string representation for now
            tb = f"{exc.type.__name__}: {exc.value}"
        
        data = {
            "service": SERVICE_NAME,
            "level": record["level"].name,
            "message": record["message"],
            "traceback": tb,
            "created_at": record["time"].isoformat()
        }
        
        try:
            # Only enqueue if we have a running loop, otherwise we might hang or crash
            asyncio.get_running_loop()
            self.queue.put_nowait(data)
        except RuntimeError:
            pass

rabbit_sink = RabbitMQSink()

def setup_logger():
    logger.remove()
    
    # Console
    logger.add(sys.stderr, level="INFO")
    
    # File
    logger.add(
        "logs/interactions.log", 
        rotation="10 MB", 
        compression="zip", 
        level="INFO", 
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    )
    
    # RabbitMQ Sink (Only Errors)
    logger.add(rabbit_sink.sink, level="ERROR")

async def start_log_handler():
    await rabbit_sink.start()

async def stop_log_handler():
    await rabbit_sink.stop()
