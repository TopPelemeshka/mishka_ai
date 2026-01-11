import httpx
import json
from loguru import logger
from src.config import settings

async def check_hard_rules(message: dict) -> bool:
    """
    Returns True if the bot MUST reply.
    Rules:
    1. Private chat
    2. Reply to bot's message
    3. Mention of bot's username
    """
    text = message.get("text", "") or ""
    chat_type = message.get("chat", {}).get("type", "unknown")
    reply_to = message.get("reply_to_message", {})
    
    # 1. Private Chat
    if chat_type == "private":
        logger.info("Hard Rule: Private Chat")
        return True
        
    # 2. Reply to Bot
    if reply_to:
        from_user = reply_to.get("from", {})
        if from_user.get("is_bot") and from_user.get("username") == settings.BOT_USERNAME:
             logger.info("Hard Rule: Reply to Bot")
             return True
             
    # 3. Mention
    if f"@{settings.BOT_USERNAME}" in text:
        logger.info("Hard Rule: Bot Mention")
        return True
        
    return False

async def check_soft_rules(message: dict) -> bool:
    """
    Uses LLM to judge relevance.
    """
    text = message.get("text", "")
    if not text:
        return False

    # Get Context (Optional, skipping for MVP speed unless critical. User requested it.)
    # context = await get_context(message['chat']['id']) 
    # For now, let's judge based on the message itself to keep latency low, 
    # or implementing simple context fetch if needed.
    # User instruction: "Load context (last 5 messages) from mishka-memory"
    
    try:
        # Fetch Context
        async with httpx.AsyncClient() as client:
            # Assuming mishka-memory has GET /context/{chat_id}?limit=5
            # Current API: GET /context?user_id=...&limit=...
            # The message dict structure from Telegram usually has chat_id, user_id.
            chat_id = message.get("chat", {}).get("id")
            context_str = ""
            if chat_id:
                try:
                    res = await client.get(f"{settings.MEMORY_API_URL}/context", params={"user_id": chat_id, "limit": 5}, timeout=2.0)
                    if res.status_code == 200:
                        history = res.json().get("history", [])
                        context_str = "\n".join([f"{m['role']}: {m['content']}" for m in history])
                except Exception as e:
                    logger.warning(f"Failed to fetch context: {e}")

        # LLM Judge
        prompt = f"""
        You are an AI assistant named 'Mishka' (Мишка).
        Your aliases: Миш, Миша, Mish, Misha, Bear, Потапыч.
        
        Decide if you should reply to the last message in a Group Chat.
        
        Context:
        {context_str}
        
        Last Message: "{text}"
        
        Criteria:
        - Reply IMMEDIATELY (Score 100) if the user addresses you by Name or Alias (e.g. "Миш, ты тут?", "Mishka help").
        - Reply (Score 80+) if the user asks a question relevant to you or general knowledge.
        - Reply (Score 75+) if the user is venting/emotional and a supportive comment fits the persona.
        - Ignore (Score < 50) short, irrelevant, or phatic expressions (e.g. "ok", "lol") unless they address you.
        - Ignore (Score < 30) internal discussions between other people if not relevant to you.
        
        Return JSON: {{"score": 0-100, "reason": "why"}}
        """
        
        payload = {
            "model": settings.LLM_MODEL, 
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(settings.LLM_PROVIDER_URL, json=payload, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                # Clean markdown json if present
                if "```json" in content:
                    content = content.replace("```json", "").replace("```", "")
                
                result = json.loads(content)
                score = result.get("score", 0)
                reason = result.get("reason", "no reason")
                
                logger.info(f"Soft Rule Judge: Score {score}, Reason: {reason}")
                return score >= settings.INITIATIVE_THRESHOLD
            else:
                logger.error(f"LLM Judge failed: {resp.status_code} {resp.text}")
                return False
                
    except Exception as e:
        logger.error(f"Soft Rule Error: {e}")
        return False
