from typing import TypedDict, Union
from fastapi import FastAPI, HTTPException
from app.models.chat_models import UserChatRequest, ChatHistory, ChatMessage
import uuid
from phoenix.otel import register
from langchain.messages import HumanMessage, AIMessage
from app.agents.sql_agent.sql_agent_v2 import agent
from app.agents.api_agent.tools import jwt_token_context

tracer_provider = register(project_name="Chat API", auto_instrument=True)

app = FastAPI(
    title="Auction Chat API",
    description="Chat interface for the auction e‑commerce system.",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    openapi_url="/openapi.json",
)

# In-memory chat sessions storage
chat_sessions = {}


class State(TypedDict):
    messages: list[Union[HumanMessage, AIMessage]]
    metadata: dict


@app.post("/chat")
def new_chat(request: UserChatRequest):
    """Create a new chat session."""
    chat_id = str(uuid.uuid4())
    context = {
        "messages": [],
        "metadata": {
            "user_id": request.user_id,
            "email": request.email,
            "username": request.username,
            "first_name": request.first_name,
            "jwt_token": request.jwt_token,
        },
    }
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

    jwt_value = context.get("metadata", {}).get("jwt_token", "") or ""
    token_scope = jwt_token_context.set(jwt_value)
    try:
        result = agent.invoke(context)
    finally:
        jwt_token_context.reset(token_scope)
    chat_sessions[chat_id] = result

    # Get last AI response
    ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
    response = ai_messages[-1].content if ai_messages else "No response"

    return {"message": response}


# from typing import Union
# from fastapi import FastAPI, HTTPException
# from app.models.chat_models import UserChatRequest, ChatHistory, ChatMessage
# import uuid
# from phoenix.otel import register
# from langchain.messages import HumanMessage, AIMessage
# from app.agents.supervisor_agent.supervisor_agent_v2 import (
#     meta_agent,
#     create_initial_context,
# )
# from app.agents.sql_agent.sql_agent_v2 import agent

# tracer_provider = register(project_name="Chat API", auto_instrument=True)

# app = FastAPI()

# # In-memory chat sessions storage
# chat_sessions = {}


# @app.post("/chat")
# def new_chat(request: UserChatRequest):
#     """Create a new chat session."""
#     chat_id = str(uuid.uuid4())
#     context = create_initial_context(user_id=request.user_id)
#     context["metadata"].update(
#         {
#             "email": request.email,
#             "username": request.username,
#             "first_name": request.first_name,
#             "jwt_token": request.jwt_token,
#         }
#     )
#     chat_sessions[chat_id] = context
#     return {"chat_id": chat_id}


# @app.get("/chat/{chat_id}")
# def get_message_history(chat_id: str):
#     """Get message history for a chat session."""
#     if chat_id not in chat_sessions:
#         raise HTTPException(status_code=404, detail="Chat session not found")

#     context = chat_sessions[chat_id]
#     messages = []
#     for msg in context["messages"]:
#         if isinstance(msg, HumanMessage):
#             messages.append({"role": "user", "content": msg.content})
#         elif isinstance(msg, AIMessage):
#             messages.append({"role": "assistant", "content": msg.content})

#     return {"chat_id": chat_id, "messages": messages}


# @app.post("/chat/{chat_id}/message")
# def message(chat_id: str, request: ChatMessage):
#     """Send a message and get AI response."""
#     if chat_id not in chat_sessions:
#         raise HTTPException(status_code=404, detail="Chat session not found")

#     context = chat_sessions[chat_id]
#     context["messages"].append(HumanMessage(content=request.message))
#     context["api_agent_attempted"] = False
#     context["needs_sql_fallback"] = False

#     result = meta_agent.invoke(context)
#     chat_sessions[chat_id] = result

#     # Get last AI response
#     ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
#     response = ai_messages[-1].content if ai_messages else "No response"

#     return {"message": response}
