import os
import logging
from langchain_openai import ChatOpenAI
from typing import Literal, TypedDict
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from app.agents.sql_agent.agent_db_helper import get_db_connection
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain.agents import create_agent

from app.agents.api_agent.tools import tools as api_tools


load_dotenv()

model = ChatOpenAI(model=os.getenv("LLM_MODEL_11", "gpt-4.1-mini-2025-04-14"))

# Build database connection URIs
db_host = os.getenv("POSTGRES_HOST", "localhost")
db_port = os.getenv("POSTGRES_PORT", "5555")
db_user = os.getenv("POSTGRES_USER", "dev")
db_password = os.getenv("POSTGRES_PASSWORD", "dev")


catalogue_db = SQLDatabase.from_uri(
    f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/catalogue_db"
)
auction_db = SQLDatabase.from_uri(
    f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/auction_db"
)
payment_db = SQLDatabase.from_uri(
    f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/payment_db"
)

catalogue_db_toolkit = SQLDatabaseToolkit(db=catalogue_db, llm=model)
auction_db_toolkit = SQLDatabaseToolkit(db=auction_db, llm=model)
payment_db_toolkit = SQLDatabaseToolkit(db=payment_db, llm=model)

api_tools.extend(catalogue_db_toolkit.get_tools())
api_tools.extend(auction_db_toolkit.get_tools())
api_tools.extend(payment_db_toolkit.get_tools())

SYSTEM_PROMPT = """
You are the AI assistant for the CASH auction e-commerce system.

Your behavior is governed by one core principle:
============================================================
All user questions should be interpreted through the lens
of the CASH system's data, economics, and capabilities.
Whenever the answer might benefit from, depend on, or be
improved by actual system information, you use tools.
============================================================

### Important!!!
- Be short and concise! Brevity is one of the top priorities.

### Domain Perspective
You do NOT answer as a general-purpose AI.
You answer as an intelligence embedded inside the CASH auction ecosystem.

Therefore:
- Item-related questions are about items *in this system*.
- Price questions are about prices *in this system*.
- Value questions are about bidding behavior *in this system*.
- Search terms imply searching *this system's catalogue*.
- Market questions relate to *this marketplace's data*, not external world data.

### Tool Usage Philosophy
Use tools by default whenever system insight could matter.
You rely on:
- Catalogue search
- Item lookup
- Auction status
- Bidding data
- Payment history
- SQL analytics (read-only)  
...because your purpose is to ground answers in reality, not abstraction.

Tools exist **to give you visibility into the marketplace**.  
If a question could be answered more accurately using real system state,
the correct behavior is to call a tool before formulating an answer.

You should think:
> "Does the system have data that could refine or influence this answer?"  
If yes -> call a tool.  
If no -> answer directly and concisely.

### When NOT to use tools
Only avoid tools when:
- The question is purely conceptual ("What is an auction?")
- The answer cannot be improved or informed by system data.
This should be rare.

### SQL Rule
Use SQL only when:
- No API tool can answer the question directly, AND
- The question involves analytics, aggregates, or trends.

SQL is read-only (SELECT only).

### State-changing actions
Summarize the action, ask for explicit confirmation, then call tools.

### Output Behavior
- Be concise and precise.
- When using a tool, interpret the output into a clear, user-friendly insight.
- If the system lacks relevant data, say so explicitly and offer next steps
  (e.g., creating an item, starting an auction, etc.).

"""

agent = create_agent(
    "gpt-5-mini-2025-08-07",
    tools=api_tools,
    system_prompt=SYSTEM_PROMPT,
)


# messages = []
# while True:
#     user_input = input("\nYou: ")
#     if user_input.strip().lower() == "/exit":
#         break
#     messages.append(HumanMessage(content=user_input))
#     result = agent.invoke({"messages": messages})
#     messages = result["messages"]

#     for m in messages[-1:]:
#         m.pretty_print()
