import os
import httpx
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from loguru import logger

class AgentState(TypedDict):
    messages: List[BaseMessage]

LLM_PROVIDER_URL = os.getenv("LLM_PROVIDER_URL", "http://mishka-llm-provider:8000/v1/chat/completions")
SYSTEM_PROMPT = "Ты дружелюбный бот Мишка. Отвечай кратко и с юмором."

async def agent_node(state: AgentState):
    messages = state["messages"]
    
    # Convert messages to format expected by LLM Provider
    # Assuming the provider expects OpenAI-like format: [{"role": "user", "content": "..."}]
    formatted_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    for msg in messages:
        if isinstance(msg, HumanMessage):
            formatted_messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
             formatted_messages.append({"role": "model", "content": msg.content}) # Gemini uses 'model' role often, or 'assistant'

    payload = {
        "model": "gemini-pro", # This might need config
        "messages": formatted_messages
    }
    
    logger.debug(f"Sending request to LLM Provider: {LLM_PROVIDER_URL}")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(LLM_PROVIDER_URL, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            
            # Extract content from response (OpenAI format approximation)
            # Adjust based on actual provider response structure from previous step!
            # Provider returns: {"choices": [{"message": {"content": "..."}}]}
            content = data["choices"][0]["message"]["content"]
            
            return {"messages": [AIMessage(content=content)]}
            
        except Exception as e:
            logger.error(f"LLM Provider call failed: {e}")
            return {"messages": [AIMessage(content="Ой, что-то в голове помутилось... (Ошибка LLM)")]}

# Build Graph
builder = StateGraph(AgentState)
builder.add_node("agent", agent_node)
builder.set_entry_point("agent")
builder.add_edge("agent", END)

graph = builder.compile()
