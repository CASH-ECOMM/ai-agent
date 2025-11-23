import os
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from typing import Literal

from langchain.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from dotenv import load_dotenv
from IPython.display import Image, display
from langchain_core.runnables.graph import CurveStyle, MermaidDrawMethod, NodeStyles

load_dotenv()


# --- PostgreSQL connection setup ---
import getpass

model = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4.1-mini-2025-04-14"))

# Get Postgres connection info from environment or prompt
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5555")
PG_USER = os.getenv("PG_USER", "dev")
PG_PASSWORD = os.getenv("PG_PASSWORD", "dev")
PG_URL = os.getenv("PG_URL", "")


def get_db(database: str):
    if PG_URL:
        uri = PG_URL
    else:
        uri = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{database}"
    db = SQLDatabase.from_uri(uri)
    print(f"Connected to DB: {database}")
    print(f"Dialect: {db.dialect}")
    print(f"Available tables: {db.get_usable_table_names()}")
    return db


# Example: connect to a specific database (change as needed)
DEFAULT_DB = os.getenv("PG_DATABASE", "catalogue_db")
db = get_db(DEFAULT_DB)

# Optionally, you can list all databases (requires superuser or proper rights)
# with db.run("SELECT datname FROM pg_database WHERE datistemplate = false;")


toolkit = SQLDatabaseToolkit(db=db, llm=model)
tools = toolkit.get_tools()

for tool in tools:
    print(f"{tool.name}: {tool.description}\n")

get_db = Too

get_schema_tool = next(tool for tool in tools if tool.name == "sql_db_schema")
get_schema_node = ToolNode([get_schema_tool], name="get_schema")

run_query_tool = next(tool for tool in tools if tool.name == "sql_db_query")
run_query_node = ToolNode([run_query_tool], name="run_query")


# Example: create a predetermined tool call
def list_tables(state: MessagesState):
    tool_call = {
        "name": "sql_db_list_tables",
        "args": {},
        "id": "abc123",
        "type": "tool_call",
    }
    tool_call_message = AIMessage(content="", tool_calls=[tool_call])

    list_tables_tool = next(tool for tool in tools if tool.name == "sql_db_list_tables")
    tool_message = list_tables_tool.invoke(tool_call)
    response = AIMessage(f"Available tables: {tool_message.content}")

    return {"messages": [tool_call_message, tool_message, response]}


# Example: force a model to create a tool call
def call_get_schema(state: MessagesState):
    # Note that LangChain enforces that all models accept `tool_choice="any"`
    # as well as `tool_choice=<string name of tool>`.
    llm_with_tools = model.bind_tools([get_schema_tool], tool_choice="any")
    response = llm_with_tools.invoke(state["messages"])

    return {"messages": [response]}


def generate_query(state: MessagesState):
    generate_query_system_prompt = """
You are an agent designed to interact with a SQL database.
Given an input question, create a syntactically correct {dialect} query to run, but DO NOT execute it.
Return ONLY the SQL query as plain text, nothing else. Do not call any tools.
Unless the user specifies a specific number of examples they wish to obtain, always limit your query to at most {top_k} results.

You can order the results by a relevant column to return the most interesting examples in the database. Never query for all the columns from a specific table, only ask for the relevant columns given the question.

DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database.
""".format(
        dialect=db.dialect,
        top_k=5,
    )

    system_message = {
        "role": "system",
        "content": generate_query_system_prompt,
    }
    # Only generate the SQL as text, do not bind any tools
    response = model.invoke([system_message] + state["messages"])
    return {"messages": [response]}


check_query_system_prompt = """
You are a SQL expert with a strong attention to detail.
Double check the {dialect} query for common mistakes, including:
- Using NOT IN with NULL values
- Using UNION when UNION ALL should have been used
- Using BETWEEN for exclusive ranges
- Data type mismatch in predicates
- Properly quoting identifiers
- Using the correct number of arguments for functions
- Casting to the correct data type
- Using the proper columns for joins

If there are any of the above mistakes, rewrite the query. If there are no mistakes,
just reproduce the original query.

You will call the appropriate tool to execute the query after running this check.
""".format(
    dialect=db.dialect
)


def check_query(state: MessagesState):
    tool_call = state["messages"][-1].tool_calls[0]

    system_message = {
        "role": "system",
        "content": check_query_system_prompt,
    }
    # Generate an artificial user message to check
    user_message = {
        "role": "user",
        "content": tool_call["args"]["query"],
    }

    llm_with_tools = model.bind_tools([run_query_tool], tool_choice="any")
    response = llm_with_tools.invoke([system_message, user_message])
    response.id = state["messages"][-1].id

    return {"messages": [response]}


def should_continue(state: MessagesState) -> Literal["__end__", "check_query"]:
    messages = state["messages"]
    last_message = messages[-1]
    if not last_message.tool_calls:
        return END  # END is still used as a value, but not in the type annotation
    else:
        return "check_query"


builder = StateGraph(MessagesState)
builder.add_node(list_tables)
builder.add_node(call_get_schema)
builder.add_node(get_schema_node, "get_schema")
builder.add_node(generate_query)
builder.add_node(check_query)
builder.add_node(run_query_node, "run_query")

builder.add_edge(START, "list_tables")
builder.add_edge("list_tables", "call_get_schema")
builder.add_edge("call_get_schema", "get_schema")
builder.add_edge("get_schema", "generate_query")
builder.add_conditional_edges(
    "generate_query",
    should_continue,
)
builder.add_edge("check_query", "run_query")
builder.add_edge("run_query", "generate_query")

agent = builder.compile()

# with open("agent_graph.png", "wb") as f:
#     f.write(agent.get_graph().draw_mermaid_png())


question = "How many active products are "

for step in agent.stream(
    {"messages": [{"role": "user", "content": question}]},
    stream_mode="values",
):
    step["messages"][-1].pretty_print()
