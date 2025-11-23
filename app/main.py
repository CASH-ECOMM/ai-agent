from typing import Union
from fastapi import FastAPI
from app.models.chat_models import UserChatRequest, ChatHistory, ChatMessage
import uuid
from phoenix.otel import register

tracer_provider = register(project_name="API Agent", auto_instrument=True)

app = FastAPI()


@app.post("/chat")
def new_chat(request: UserChatRequest):
    user_info = {
        "user_id": request.user_id,
        "email": request.email,
        "username": request.username,
        "first_name": request.first_name,
    }
    return {"chat_id": uuid.uuid4()}


@app.get("/chat/{chat_id}")
def get_message_history(chat_id: int, request: ChatMessage):
    return {"chat_id": chat_id, "messages": []}


@app.post("/chat/{chat_id}/message")
def message(chat_id: int):
    return {"message": "AI response"}
