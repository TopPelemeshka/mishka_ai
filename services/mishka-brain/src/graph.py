import os
import httpx
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from loguru import logger

from src.utils import get_context

class AgentState(TypedDict):
    messages: List[BaseMessage]
    chat_id: int

LLM_PROVIDER_URL = os.getenv("LLM_PROVIDER_URL", "http://mishka-llm-provider:8000/v1/chat/completions")
SYSTEM_PROMPT = "Ты дружелюбный бот Мишка. Отвечай кратко и с юмором."

async def agent_node(state: AgentState):
    messages = state["messages"]
    chat_id = state.get("chat_id")
    
    # Load Context from Memory
    history_messages = []
    if chat_id:
        context = await get_context(chat_id)
        # Parse history
        for msg in context.get("history", []):
            role = msg["role"] # "user" or "assistant"
            content = msg["content"]
            if role == "user":
                history_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                history_messages.append({"role": "model", "content": content})
    
    # Convert current session messages
    current_messages = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
             # Skip if duplicate of last history message
             role = "user"
             content = msg.content
             
             # Check if this exact message is already the last one in history
             if history_messages:
                 last_history = history_messages[-1]
                 if last_history["role"] == role and last_history["content"] == content:
                     logger.debug(f"Skipping duplicate message in prompt: {content[:20]}...")
                     continue

             current_messages.append({"role": role, "content": content})
        elif isinstance(msg, AIMessage):
             current_messages.append({"role": "model", "content": msg.content})

    # Combine: System + History + Current
    formatted_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    formatted_messages.extend(history_messages)
    formatted_messages.extend(current_messages)

    payload = {
        "model": os.getenv("LLM_MODEL", "gemini-pro"),
        "messages": formatted_messages
    }
    
    logger.debug(f"Sending request to LLM Provider: {LLM_PROVIDER_URL}")
    
    async with httpx.AsyncClient() as client:
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            else:
                logger.warning("GEMINI_API_KEY not found in environment variables")
                
            response = await client.post(LLM_PROVIDER_URL, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            
            # Extract content from response (OpenAI format approximation)
            # Adjust based on actual provider response structure from previous step!
            # Provider returns: {"choices": [{"message": {"content": "..."}}]}
            content = data["choices"][0]["message"]["content"]
            
            return {"messages": [AIMessage(content=content)]}
            
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM Provider HTTP status error: {e.response.status_code} - {e.response.text}")
            return {"messages": [AIMessage(content=f"Ошибка LLM Provider: {e.response.status_code}")]}
        except Exception as e:
            logger.exception(f"LLM Provider unexpected error: {e}")
            return {"messages": [AIMessage(content="Ой, что-то в голове помутилось... (Ошибка Brain)")]}

# Build Graph
builder = StateGraph(AgentState)
builder.add_node("agent", agent_node)
builder.set_entry_point("agent")
builder.add_edge("agent", END)

graph = builder.compile()
