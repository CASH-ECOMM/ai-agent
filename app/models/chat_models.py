from pydantic import BaseModel


class UserChatRequest(BaseModel):
    user_id: int
    email: str
    username: str
    first_name: str


class ChatMessage(BaseModel):
    message: str


class ChatHistory(BaseModel):
    messages: list[ChatMessage]
