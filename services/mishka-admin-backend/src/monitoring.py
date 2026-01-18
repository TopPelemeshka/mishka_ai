import httpx
import asyncio
import json
import logging
from datetime import datetime
from sqlalchemy.future import select
from src.database import AsyncSessionLocal
from src.models import ServiceHealth, SystemError
from src.events import producer # We need RabbitMQ connection, reusing producer might be weird if it's strictly producer. 
# Better to use a separate consumer logic or reuse rmq client if available.
# mishka-admin-backend has `src/events.py`? Let's assume it has RMQ logic.
# If not, I'll use aio_pika directly here.

logger = logging.getLogger(__name__)

# HTTP Services to monitor
SERVICES = [
    {"name": "mishka-brain", "url": "http://mishka-brain:8000/health"},
    {"name": "mishka-memory", "url": "http://mishka-memory:8000/health"},
    {"name": "mishka-llm-provider", "url": "http://mishka-llm-provider:8000/health"},
    # mishka-personality has no explicit health endpoint? FastAPI adds /docs but not /health by default unless defined.
    # checking... mishka-personality/src/main.py usually has one? 
    # If not I should rely on root / or /docs/oauth2-redirect or similar, or just assume it fails.
    # Most services I wrote have /health.
    {"name": "mishka-personality", "url": "http://mishka-personality:8000/health"},
    {"name": "mishka-archivist", "url": "http://mishka-archivist:8000/health"},
    {"name": "mishka-dreamer", "url": "http://mishka-dreamer:8000/health"},
    {"name": "tool-weather", "url": "http://tool-weather:8000/health"},
]

async def check_health():
    """Periodic job to ping services."""
    logger.info("Running Health Checks...")
    async with httpx.AsyncClient(timeout=3.0) as client:
        for svc in SERVICES:
            status = "offline"
            details = ""
            try:
                resp = await client.get(svc["url"])
                if resp.status_code == 200:
                    status = "healthy"
                    details = json.dumps(resp.json())
                else:
                    status = "unhealthy"
                    details = f"Status: {resp.status_code}"
            except Exception as e:
                status = "offline"
                details = str(e)
            
            # Save to DB
            async with AsyncSessionLocal() as db:
                # Upsert
                result = await db.execute(select(ServiceHealth).where(ServiceHealth.service_name == svc["name"]))
                existing = result.scalars().first()
                
                if existing:
                    existing.status = status
                    existing.last_seen = datetime.utcnow()
                    existing.details = details
                else:
                    db.add(ServiceHealth(service_name=svc["name"], status=status, details=details))
                
                await db.commit()

async def save_error(data: dict):
    """Saves error to DB."""
    try:
        async with AsyncSessionLocal() as db:
            err = SystemError(
                service=data.get("service", "unknown"),
                level=data.get("level", "ERROR"),
                message=data.get("message", ""),
                traceback=data.get("traceback", "")
            )
            db.add(err)
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to save error: {e}")

# Error Consumer Logic
import aio_pika
from src.config import settings

async def start_error_consumer():
    """Starts RabbitMQ consumer for system_errors."""
    try:
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await connection.channel()
        queue = await channel.declare_queue("system_errors", durable=True)
        
        async def process_message(message: aio_pika.IncomingMessage):
            async with message.process():
                data = json.loads(message.body.decode())
                await save_error(data)
                
        await queue.consume(process_message)
        logger.info("Started System Error Consumer")
        return connection
    except Exception as e:
        logger.error(f"Failed to start error consumer: {e}")
        return None
