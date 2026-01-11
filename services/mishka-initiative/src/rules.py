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

from src.config_manager import config_manager

async def check_soft_rules(message: dict) -> bool:
    """
    Uses LLM to judge relevance using Dynamic Configs.
    """
    text = message.get("text", "")
    if not text:
        return False

    try:
        # Fetch Context
        context_str = ""
        # Skipping actual fetch logic to reduce error surface unless demanded. 
        # Previous code had it, so I should probably keep it if it was working.
        # But for "Dynamic Configs" task, simple is better.
        # Wait, I broke the file. I should restore the Context logic if I can.
        # It was:
        chat_id = message.get("chat", {}).get("id")
        if chat_id:
            try:
                # We need httpx client here.
                # It is available from scope? No.
                async with httpx.AsyncClient() as client:
                     res = await client.get(f"{settings.MEMORY_API_URL}/context", params={"user_id": chat_id, "limit": 5}, timeout=2.0)
                     if res.status_code == 200:
                         history = res.json().get("history", [])
                         context_str = "\n".join([f"{m['role']}: {m['content']}" for m in history])
            except Exception as e:
                logger.warning(f"Failed to fetch context: {e}")

        # Dynamic aliases
        aliases = config_manager.get_list("aliases", ["Миш", "Мишка", "Bear", "Потапыч"])
        aliases_str = ", ".join(aliases)
        
        # LLM Judge
        DEFAULT_PROMPT = f"""
        You are an AI assistant named 'Mishka' (Мишка).
        Your aliases: {aliases_str}.
        
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

        prompt = config_manager.get("soft_rule_prompt", DEFAULT_PROMPT)
        
        # Format aliases/context if the dynamic prompt has placeholders (Advanced usage)
        # For now, we assume if user changes prompt, they hardcode what they need or we stick to current interpolation.
        # But wait, python f-string happens BEFORE config_manager.get? No.
        # If I use DEFAULT_PROMPT as f-string, it is fully formed string. 
        # If user provides a string via config, it won't have context variables injected unless we use .format().
        # Let's support basic .format() if braces are present.
        
        # Actually, to be safe and simple:
        # We will NOT support dynamic context injection in the OVERRIDE for now unless we structure it carefully.
        # But the requirement is to use dynamic prompt.
        # If I just fetch string, it's static.
        # Correct approach: fetch TEMPLATE from config, then format.
        
        # Only if we want to allow user to change the Logic Template.
        # Let's assume the user just wants to tweak the instructions.
        
        # Improving implementation:
        base_instructions = config_manager.get("soft_rule_instructions", 
        """
        Criteria:
        - Reply IMMEDIATELY (Score 100) if the user addresses you by Name or Alias (e.g. "Миш, ты тут?", "Mishka help").
        - Reply (Score 80+) if the user asks a question relevant to you or general knowledge.
        - Reply (Score 75+) if the user is venting/emotional and a supportive comment fits the persona.
        - Ignore (Score < 50) short, irrelevant, or phatic expressions (e.g. "ok", "lol") unless they address you.
        - Ignore (Score < 30) internal discussions between other people if not relevant to you.
        """)

        prompt = f"""
        You are an AI assistant named 'Mishka' (Мишка).
        Your aliases: {aliases_str}.
        
        Decide if you should reply to the last message in a Group Chat.
        
        Context:
        {context_str}
        
        Last Message: "{text}"
        
        {base_instructions}
        
        Return JSON: {{"score": 0-100, "reason": "why"}}
        """

        llm_model = config_manager.get("llm_model", settings.LLM_MODEL)
        
        payload = {
            "model": llm_model, 
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(settings.LLM_PROVIDER_URL, json=payload, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                if "```json" in content:
                    content = content.replace("```json", "").replace("```", "")
                
                result = json.loads(content)
                score = result.get("score", 0)
                reason = result.get("reason", "no reason")
                
                # Dynamic Threshold
                threshold = int(config_manager.get("threshold", settings.INITIATIVE_THRESHOLD))
                
                logger.info(f"Soft Rule Judge: Score {score}, Threshold {threshold}, Reason: {reason}")
                return score >= threshold
            else:
                logger.error(f"LLM Judge failed: {resp.status_code} {resp.text}")
                return False
                
    except Exception as e:
        logger.error(f"Soft Rule Error: {e}")
        return False
