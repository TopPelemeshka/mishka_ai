import os
import httpx
import json
from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from loguru import logger

from src.utils import get_context, list_tools

class AgentState(TypedDict):
    messages: List[BaseMessage]
    chat_id: int
    tools: List[dict]
    files: List[str] # List of file paths for the current turn

LLM_PROVIDER_URL = os.getenv("LLM_PROVIDER_URL", "http://mishka-llm-provider:8000/v1/chat/completions")
SYSTEM_PROMPT_BASE = "Ты дружелюбный бот Мишка. Отвечай кратко и с юмором."

async def agent_node(state: AgentState):
    messages = state["messages"]
    chat_id = state.get("chat_id")
    
    # 1. Load Tools (Registry)
    tools = await list_tools()
    
    # 2. Load Context from Memory (History)
    history_messages = []
    if chat_id:
        context = await get_context(chat_id)
        for msg in context.get("history", []):
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                history_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                history_messages.append({"role": "model", "content": content})
            elif role == "tool":
                # We can present tool results as system or model messages depending on LLM
                # For Gemini, we might want to present it as model/assistant info or system
                history_messages.append({"role": "user", "content": f"Результат инструмента: {content}"})

    # 3. Construct System Prompt with Tools
    tools_desc = ""
    if tools:
        tools_desc = "\n\nТебе доступны инструменты:\n" + json.dumps(tools, ensure_ascii=False, indent=2)
        tools_desc += "\nЕсли нужно вызвать инструмент, верни ТОЛЬКО JSON: {\"tool\": \"name\", \"args\": {...}}"
    
    system_prompt = SYSTEM_PROMPT_BASE + tools_desc
    
    # 4. Convert currentTurn messages and deduplicate
    current_messages = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            if history_messages and history_messages[-1]["content"] == msg.content:
                continue
            current_messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            current_messages.append({"role": "model", "content": msg.content})

    formatted_messages = [{"role": "system", "content": system_prompt}]
    formatted_messages.extend(history_messages)
    formatted_messages.extend(current_messages)

    # Attach files to the last message if available and it is a user message
    files = state.get("files", [])
    if files and formatted_messages:
        last_msg = formatted_messages[-1]
        if last_msg["role"] == "user":
            last_msg["files"] = files
            logger.info(f"Attaching files to payload: {files}")

    payload = {
        "model": os.getenv("LLM_MODEL", "gemini-pro"),
        "messages": formatted_messages
    }
    
    # LOGGING: Full prompt
    logger.debug(f"=== SENDING TO LLM ===\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n======================")
    
    async with httpx.AsyncClient() as client:
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            
            response = await client.post(LLM_PROVIDER_URL, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            
            # LOGGING: LLM Response
            logger.debug(f"=== LLM RESPONSE ===\n{content}\n====================")
            
            return {"messages": [AIMessage(content=content)], "tools": tools}
            
        except Exception as e:
            logger.exception(f"LLM Provider error: {e}")
            return {"messages": [AIMessage(content="Ой, ошибка в голове...")]}

async def tool_node(state: AgentState):
    """Execute the tool call found in the last message."""
    last_msg = state["messages"][-1].content
    tools = state.get("tools", [])
    
    try:
        call = json.loads(last_msg)
        tool_name = call.get("tool")
        args = call.get("args")
        
        # Find tool endpoint
        tool_config = next((t for t in tools if t["name"] == tool_name), None)
        if not tool_config:
            return {"messages": [HumanMessage(content=f"Ошибка: Инструмент {tool_name} не найден")]}
            
        # LOGGING: Tool Call
        logger.info(f"=== EXECUTING TOOL: {tool_name} ===\nArgs: {json.dumps(args, ensure_ascii=False)}\n===============================")
        
        logger.info(f"Calling tool {tool_name} at {tool_config['endpoint']}")
        async with httpx.AsyncClient() as client:
            resp = await client.post(tool_config["endpoint"], json=args, timeout=20.0)
            resp.raise_for_status()
            result = resp.json()
            
            # LOGGING: Tool Result
            logger.info(f"=== TOOL RESULT ===\n{json.dumps(result, ensure_ascii=False, indent=2)}\n===================")
            
            # Add tool result to messages
            # We use HumanMessage here to feed it back to LLM as new info
            # We use a specific prefix to help the model distinguish from user chat
            return {"messages": [HumanMessage(content=f"[System] Результат инструмента '{tool_name}': {json.dumps(result, ensure_ascii=False)}")]}
            
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return {"messages": [HumanMessage(content=f"Ошибка выполнения инструмента: {str(e)}")]}

def should_continue(state: AgentState):
    """Check if LLM wants to call a tool or talk to user."""
    last_msg = state["messages"][-1].content
    try:
        # Simple heuristic: if it's valid JSON with 'tool' key, it's a tool call
        data = json.loads(last_msg)
        if isinstance(data, dict) and "tool" in data:
            return "tools"
    except:
        pass
    return "end"

# Build Graph
builder = StateGraph(AgentState)
builder.add_node("agent", agent_node)
builder.add_node("tools", tool_node)

builder.set_entry_point("agent")

# Logic: agent -> tools (if tool call) -> agent (to summarize) -> END (if text)
builder.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        "end": END
    }
)

builder.add_edge("tools", "agent")

graph = builder.compile()
