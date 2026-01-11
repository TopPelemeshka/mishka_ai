
import asyncio
import aio_pika
import json
import os

# Config from Env or Defaults
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

async def inject_message(text: str, chat_type: str = "group", is_reply_to_bot: bool = False):
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        
        # publish to chat_events (simulate Gateway)
        queue_name = "chat_events"
        
        # Construct message payload simulating Telegram update
        msg_payload = {
            "text": text,
            "chat": {"id": 12345, "type": chat_type},
            "from": {"id": 999, "username": "tester", "is_bot": False},
            "message_id": 101
        }
        
        if is_reply_to_bot:
            msg_payload["reply_to_message"] = {
                "from": {"id": 888, "username": "mishka_bot", "is_bot": True},
                "text": "Previously..."
            }
            
        await channel.default_exchange.publish(
            aio_pika.Message(body=json.dumps(msg_payload).encode()),
            routing_key=queue_name
        )
        print(f"Sent to {queue_name}: {text}")

async def listen_brain_tasks(timeout: int = 5):
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue("brain_tasks", durable=True)
        
        print(f"Listening to brain_tasks for {timeout}s...")
        try:
            # Simple consume one message
            msg = await asyncio.wait_for(queue.get(fail=False), timeout=timeout)
            if msg:
                print(f"RECEIVED in brain_tasks: {msg.body.decode()}")
                await msg.ack()
                return True
            else:
                print("No message received.")
                return False
        except asyncio.TimeoutError:
             print("Timeout: No message received.")
             return False

async def run_tests():
    # Purge queues to ensure clean state
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        q1 = await channel.declare_queue("brain_tasks", durable=True)
        await q1.purge()
        q2 = await channel.declare_queue("chat_events", durable=True)
        await q2.purge()
        print("Queues purged.")

    print("--- 1. Hard Rule Test: @mishka_bot mention ---")
    await inject_message("Hello @mishka_bot how are you?")
    res = await listen_brain_tasks()
    if not res: print("FAILURE: Hard Rule Mention missed")
    else: print("SUCCESS: Hard Rule Mention passed")
    
    print("\n--- 2. Hard Rule Test: Reply to Bot ---")
    await inject_message("That's true", is_reply_to_bot=True)
    res = await listen_brain_tasks()
    if not res: print("FAILURE: Hard Rule Reply missed")
    else: print("SUCCESS: Hard Rule Reply passed")

    print("\n--- 3. Soft Rule Test: Irrelevant message ---")
    await inject_message("Just talking about weather with friends")
    # This DEPENDS on the LLM judge. If mocked or LLM says irrelevant (probably score < 70).
    # We expect Silence (Timeout).
    res = await listen_brain_tasks(timeout=5)
    if not res: print("SUCCESS: Irrelevant message dropped (Timeout as expected)")
    else: print("WARNING: Irrelevant message passed (Score >= 70?)")

    print("\n--- 4. Soft Rule Test: RELEVANT message ---")
    await inject_message("Mishka, what is the capital of France?")
    res = await listen_brain_tasks(timeout=10)
    if res: print("SUCCESS: Relevant message passed")
    else: print("FAILURE: Relevant message dropped (LLM Error or Score < 70)")

if __name__ == "__main__":
    asyncio.run(run_tests())
