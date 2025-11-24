import os
from langgraph.graph import START, END, MessagesState, StateGraph
from langchain.messages import HumanMessage, SystemMessage
from typing import Literal, TypedDict

# Import your existing agents
from app.agents.api_agent.api_agent import agent as api_agent
from app.agents.sql_agent.sql_agent import agent as sql_agent, SQLAgentState
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

from phoenix.otel import register

tracer_provider = register(project_name="API Agent", auto_instrument=True)


load_dotenv()
model = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4.1-mini-2025-04-14"))


# --- 1. Define conversation context ---
class ConversationContext(TypedDict):
    messages: list
    current_task: str  # 'posting_item', 'analytics_query', etc.
    last_agent_used: str  # 'api_agent' or 'sql_agent'
    metadata: dict  # e.g., user_id, last_item_id


# Initialize context
def create_initial_context(user_id: int):
    return ConversationContext(
        messages=[],
        current_task="",
        last_agent_used="",
        metadata={"user_id": user_id},
    )


# --- 2. Agent chooser ---
def choose_agent(state: ConversationContext, user_input: str) -> str:
    """Decide which agent should handle the request."""
    prompt = f"""
    You are a routing assistant. Decide if the user input should be handled by the API agent (for posting items, bidding, getting auction info)
    or by the SQL agent (for analytics, stats, database queries).

    Input: {user_input}

    Answer ONLY 'api_agent' or 'sql_agent'.
    """
    response = model.invoke([HumanMessage(content=prompt)])
    agent_choice = response.content.strip().lower()
    if agent_choice not in ["api_agent", "sql_agent"]:
        return "api_agent"  # default fallback
    return agent_choice


# --- 3. Adapter nodes to call existing agents ---
def run_api_agent(state: ConversationContext):
    """Wrap the API agent in a callable node."""
    # Extract the last user message
    user_input = state["messages"][-1].content if state["messages"] else ""

    result = api_agent.invoke({"messages": state["messages"]})
    # Replace messages with agent result
    state["messages"] = result["messages"]
    state["last_agent_used"] = "api_agent"
    return state


def run_sql_agent(state: ConversationContext):
    """Wrap the SQL agent in a callable node."""
    # Extract the last user message
    user_input = state["messages"][-1].content if state["messages"] else ""

    sql_state: SQLAgentState = {
        "user_query": user_input,
        "user_id": state["metadata"].get("user_id"),
        "generated_sql": "",
        "target_database": "",
        "validation_result": {},
        "query_result": "",
        "error": "",
    }
    sql_result = sql_agent.invoke(sql_state)
    # Append query result or error to messages
    if sql_result.get("query_result"):
        state["messages"].append(HumanMessage(content=sql_result["query_result"]))
    elif sql_result.get("error"):
        state["messages"].append(HumanMessage(content=sql_result["error"]))
    state["last_agent_used"] = "sql_agent"
    return state


# --- 4. Router node ---
def meta_router_node(state: ConversationContext):
    """Decide which agent to route to based on the user input."""
    last_message = state["messages"][-1].content
    agent_choice = choose_agent(state, last_message)
    state["metadata"]["chosen_agent"] = agent_choice
    return state


# --- 5. Conditional routing function ---
def route_to_agent(state: ConversationContext) -> Literal["api_node", "sql_node"]:
    if state["metadata"].get("chosen_agent") == "sql_agent":
        return "sql_node"
    return "api_node"


# --- 6. Build the Meta-Agent Graph ---
graph = StateGraph(ConversationContext)

graph.add_node("router", meta_router_node)
graph.add_node("api_node", run_api_agent)
graph.add_node("sql_node", run_sql_agent)

# Define edges
graph.add_edge(START, "router")
graph.add_conditional_edges("router", route_to_agent, ["api_node", "sql_node"])

# End after agent processes the message (no loop back)
graph.add_edge("api_node", END)
graph.add_edge("sql_node", END)

meta_agent = graph.compile()

# --- 7. Example Usage ---
if __name__ == "__main__":
    # Interactive loop example
    context = create_initial_context(user_id=1)

    print("=== Meta-Agent Chat (type '/exit' to quit) ===\n")

    while True:
        user_input = input("You: ")
        if user_input.strip().lower() == "/exit":
            break

        context["messages"].append(HumanMessage(content=user_input))
        result = meta_agent.invoke(context)
        context = result

        print("\nAgent: ", end="")
        for m in context["messages"][-1:]:
            m.pretty_print()
        print()
