from typing import Union
from fastapi import FastAPI, HTTPException
from app.models.chat_models import UserChatRequest, ChatHistory, ChatMessage
import uuid
from phoenix.otel import register
from langchain.messages import HumanMessage, AIMessage
from app.agents.supervisor_agent.supervisor_agent_v2 import (
    meta_agent,
    create_initial_context,
)

tracer_provider = register(project_name="Chat API", auto_instrument=True)

app = FastAPI()

# In-memory chat sessions storage
chat_sessions = {}


@app.post("/chat")
def new_chat(request: UserChatRequest):
    """Create a new chat session."""
    chat_id = str(uuid.uuid4())
    context = create_initial_context(user_id=request.user_id)
    context["metadata"].update(
        {
            "email": request.email,
            "username": request.username,
            "first_name": request.first_name,
            "jwt_token": request.jwt_token,
        }
    )
    chat_sessions[chat_id] = context
    return {"chat_id": chat_id}


@app.get("/chat/{chat_id}")
def get_message_history(chat_id: str):
    """Get message history for a chat session."""
    if chat_id not in chat_sessions:
        raise HTTPException(status_code=404, detail="Chat session not found")

    context = chat_sessions[chat_id]
    messages = []
    for msg in context["messages"]:
        if isinstance(msg, HumanMessage):
            messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            messages.append({"role": "assistant", "content": msg.content})

    return {"chat_id": chat_id, "messages": messages}


@app.post("/chat/{chat_id}/message")
def message(chat_id: str, request: ChatMessage):
    """Send a message and get AI response."""
    if chat_id not in chat_sessions:
        raise HTTPException(status_code=404, detail="Chat session not found")

    context = chat_sessions[chat_id]
    context["messages"].append(HumanMessage(content=request.message))
    context["api_agent_attempted"] = False
    context["needs_sql_fallback"] = False

    result = meta_agent.invoke(context)
    chat_sessions[chat_id] = result

    # Get last AI response
    ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
    response = ai_messages[-1].content if ai_messages else "No response"

    return {"message": response}
