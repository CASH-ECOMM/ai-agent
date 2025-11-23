from typing import Union
from fastapi import FastAPI

app = FastAPI()


@app.post("/chat")
def new_chat():
    return {"chat_id": "12345"}


@app.post("/chat/{chat_id}/message")
def message():
    return {"chat_id": "12345"}


@app.get("/chat/{chat_id}/message")
def get_messages(chat_id: int, q: Union[str, None] = None):
    return {"chat_id": chat_id, "q": q}
