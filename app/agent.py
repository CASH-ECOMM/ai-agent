import os
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from dotenv import load_dotenv

from app.prompts import get_system_prompt
from app.tools import tools

load_dotenv()

model = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "gpt-4.1-mini-2025-04-14"), temperature=0.1
)

SYSTEM_PROMPT = get_system_prompt(version=1)

agent = create_agent(
    model,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
)
