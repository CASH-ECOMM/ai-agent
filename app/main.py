from typing import TypedDict, Union
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.models.chat_models import UserChatRequest, ChatHistory, ChatMessage
import uuid
from phoenix.otel import register
from langchain.messages import HumanMessage, AIMessage, SystemMessage
from app.agent import agent
from app.tools import jwt_token_context

tracer_provider = register(project_name="Chat API Test 2", auto_instrument=True)

app = FastAPI(
    title="Auction Chat API",
    description="Chat interface for the auction e‑commerce system.",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    openapi_url="/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# In-memory chat sessions storage
chat_sessions = {}


class State(TypedDict):
    messages: list[Union[HumanMessage, AIMessage]]
    metadata: dict


@app.post("/api/chats")
def new_chat(request: UserChatRequest):
    """Create a new chat session."""
    USER_INFO_SYSTEM_PROMPT = f"""Here's user's information you might need to use when calling tools:
        - user_id: {request.user_id}
        - email: {request.email}
        - username: {request.username}
        - first_name: {request.first_name}
        """

    chat_id = str(uuid.uuid4())
    context = {
        "messages": [SystemMessage(content=USER_INFO_SYSTEM_PROMPT)],
        "metadata": {
            "jwt_token": request.jwt_token,
        },
    }
    chat_sessions[chat_id] = context
    return {"chat_id": chat_id}


@app.get("/api/chats/{chat_id}")
def get_message_history(chat_id: str):
    """Get message history for a chat session."""
    if chat_id not in chat_sessions:
        raise HTTPException(
            status_code=404, detail=f"Chat session '{chat_id}' not found"
        )

    context = chat_sessions[chat_id]
    messages = []
    for msg in context["messages"]:
        if isinstance(msg, HumanMessage):
            messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            messages.append({"role": "assistant", "content": msg.content})

    return {"chat_id": chat_id, "messages": messages}


@app.post("/api/chats/{chat_id}/message")
def message(chat_id: str, request: ChatMessage):
    """Send a message and get AI response."""
    if chat_id not in chat_sessions:
        raise HTTPException(
            status_code=404, detail=f"Chat session '{chat_id}' not found"
        )

    context = chat_sessions[chat_id]
    user_msg = HumanMessage(content=request.message)
    context["messages"].append(user_msg)
    invoke_context = {"messages": context["messages"], "metadata": context["metadata"]}
    jwt_value = context.get("metadata", {}).get("jwt_token", "") or ""
    token_scope = jwt_token_context.set(jwt_value)
    try:
        result = agent.invoke(invoke_context)
    finally:
        jwt_token_context.reset(token_scope)
    ai_response = result["messages"][-1]
    chat_sessions[chat_id]["messages"].append(ai_response)
    response_content = (
        ai_response.content if isinstance(ai_response, AIMessage) else "No response"
    )

    return {"message": response_content}
