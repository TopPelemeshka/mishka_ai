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
MEMORY_API_URL = os.getenv("MEMORY_API_URL", "http://mishka-memory:8000/facts/search")
SYSTEM_PROMPT_BASE = "Ты дружелюбный бот Мишка. Отвечай кратко и с юмором."

async def retrieve_facts(query: str):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(MEMORY_API_URL, json={"query": query, "limit": 3}, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", [])
        except Exception as e:
            logger.warning(f"Failed to retrieve facts: {e}")
    return []

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
    
    import datetime

    # 4. Convert currentTurn messages and deduplicate
    current_messages = []
    
    # helper to format message content
    def format_content(role, content, user_name=None, created_at=None):
        if role == "user":
            name = user_name or "User"
            time_str = ""
            if created_at:
                try:
                    # Try parsing ISO
                    dt = datetime.datetime.fromisoformat(created_at)
                    time_str = f" | Time: {dt.strftime('%H:%M')}"
                except:
                    pass
            return f"[User: {name}{time_str}]\n{content}"
        return content

    for msg in messages:
        if isinstance(msg, HumanMessage):
             # For current turn messages, we might not have metadata in the object itself easily
             # unless we passed it in state. But state["messages"] are usually just LangChain messages.
             # However, consumer passes input_state with messages.
             # We rely on "current" message not needing formatting because it's "now". 
             # Wait, user wants LLM to know who is speaking NOW too.
             # Logic: consumer triggers run. The last message is from user. 
             # We can't easily modify the HumanMessage object in consumer to add metadata that LangChain preserves?
             # Actually, we can just format the content in consumer before creating HumanMessage? 
             # OR we format it here if we assume it's the current user.
             # Let's keep current messages simple for now, or format them if we can.
             # Actually, the requirement says "Format message User...". 
             # Let's format history first, that's critical. 
             # Current message is usually implied to be from the active user.
             
            if history_messages and history_messages[-1]["content"] == msg.content:
                continue
            current_messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            current_messages.append({"role": "model", "content": msg.content})

    # Re-process history messages to format them
    formatted_history = []
    for msg in context.get("history", []):
         f_role = msg["role"]
         f_content = msg["content"]
         if f_role == "user":
             f_content = format_content("user", f_content, msg.get("user_name"), msg.get("created_at"))
             formatted_history.append({"role": "user", "content": f_content})
         elif f_role == "assistant":
             formatted_history.append({"role": "model", "content": f_content})
         elif f_role == "tool":
             formatted_history.append({"role": "user", "content": f"Результат инструмента: {f_content}"})

    # Dynamic System Prompt
    current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # RAG: Retrieve relevant facts
    relevant_facts = ""
    try:
        last_msg_content = messages[-1].content if messages else ""
        if last_msg_content:
            facts = await retrieve_facts(last_msg_content)
            if facts:
                relevant_facts = "\n\nНайденные факты из памяти:\n" + "\n".join([f"- {f['text']}" for f in facts])
    except Exception as e:
        logger.error(f"RAG Error: {e}")

    system_prompt = f"Current Time: {current_time_str}\n" + SYSTEM_PROMPT_BASE + relevant_facts + tools_desc

    formatted_messages = [{"role": "system", "content": system_prompt}]
    formatted_messages.extend(formatted_history)
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
