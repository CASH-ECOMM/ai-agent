import os
from langgraph.graph import START, END, MessagesState, StateGraph
from langchain.messages import HumanMessage, SystemMessage, AIMessage
from typing import Literal, TypedDict

# Import your existing agents
from app.agents.api_agent.api_agent import agent as api_agent
from app.agents.sql_agent.sql_agent import agent as sql_agent, SQLAgentState
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

from phoenix.otel import register

tracer_provider = register(project_name="Supervisor Agent V2", auto_instrument=True)


load_dotenv()
model = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4.1-mini-2025-04-14"))


# --- 1. Define conversation context ---
class ConversationContext(TypedDict):
    messages: list
    current_task: str  # 'posting_item', 'analytics_query', etc.
    last_agent_used: str  # 'api_agent' or 'sql_agent'
    api_agent_attempted: bool  # Track if API agent has been tried
    needs_sql_fallback: bool  # Flag to indicate if SQL agent is needed
    metadata: dict  # e.g., user_id, last_item_id


# Initialize context
def create_initial_context(user_id: int):
    return ConversationContext(
        messages=[],
        current_task="",
        last_agent_used="",
        api_agent_attempted=False,
        needs_sql_fallback=False,
        metadata={"user_id": user_id},
    )


# --- 2. API Agent Node (First Priority) ---
def run_api_agent(state: ConversationContext):
    """Run the API agent first to attempt fulfilling the request."""
    # Extract the last user message
    user_input = state["messages"][-1].content if state["messages"] else ""

    print(f"\n[API Agent] Processing request: {user_input[:50]}...")
    
    try:
        result = api_agent.invoke({"messages": state["messages"]})
        # Replace messages with agent result
        state["messages"] = result["messages"]
        state["last_agent_used"] = "api_agent"
        state["api_agent_attempted"] = True
        
        # Check if the API agent successfully handled the request
        # The API agent returns AIMessage with tool calls or direct responses
        last_message = state["messages"][-1]
        
        # Determine if we need SQL fallback based on the API agent's response
        if isinstance(last_message, AIMessage):
            response_content = last_message.content.lower() if last_message.content else ""
            
            # Indicators that API agent couldn't fulfill the request
            fallback_indicators = [
                "i don't have",
                "i cannot",
                "i'm unable to",
                "not available",
                "cannot provide",
                "don't have access",
                "analytics",
                "statistics",
                "query the database",
                "historical data",
                "aggregate",
                "report"
            ]
            
            # Check if response suggests the need for database queries
            needs_fallback = any(indicator in response_content for indicator in fallback_indicators)
            state["needs_sql_fallback"] = needs_fallback
            
            if needs_fallback:
                print("[API Agent] Cannot fulfill request, will route to SQL agent")
        
        return state
    except Exception as e:
        print(f"[API Agent] Error: {str(e)}, will route to SQL agent")
        state["api_agent_attempted"] = True
        state["needs_sql_fallback"] = True
        state["messages"].append(AIMessage(content=f"API agent encountered an error. Routing to SQL agent for assistance."))
        return state


# --- 3. SQL Agent Node (Fallback) ---
def run_sql_agent(state: ConversationContext):
    """Run the SQL agent when API agent cannot fulfill the request."""
    # Extract the original user message (before API agent attempted)
    user_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
    user_input = user_messages[-1].content if user_messages else ""
    
    print(f"[SQL Agent] Processing fallback request: {user_input[:50]}...")

    sql_state: SQLAgentState = {
        "user_query": user_input,
        "user_id": state["metadata"].get("user_id"),
        "generated_sql": "",
        "target_database": "",
        "validation_result": {},
        "query_result": "",
        "error": "",
    }
    
    try:
        sql_result = sql_agent.invoke(sql_state)
        
        # Append query result or error to messages
        if sql_result.get("query_result"):
            state["messages"].append(AIMessage(content=sql_result["query_result"]))
            print("[SQL Agent] Successfully provided database query results")
        elif sql_result.get("error"):
            state["messages"].append(AIMessage(content=f"SQL query error: {sql_result['error']}"))
            print(f"[SQL Agent] Error: {sql_result['error']}")
        else:
            state["messages"].append(AIMessage(content="SQL agent completed but no results were returned."))
            
        state["last_agent_used"] = "sql_agent"
    except Exception as e:
        print(f"[SQL Agent] Error: {str(e)}")
        state["messages"].append(AIMessage(content=f"SQL agent encountered an error: {str(e)}"))
    
    return state


# --- 4. Conditional routing function ---
def should_fallback_to_sql(state: ConversationContext) -> Literal["sql_node", "__end__"]:
    """Determine if we should route to SQL agent or end."""
    if state.get("needs_sql_fallback", False):
        return "sql_node"
    return "__end__"


# --- 5. Build the Sequential Agent Graph ---
# Flow: START -> API Agent -> (if needed) SQL Agent -> END
graph = StateGraph(ConversationContext)

graph.add_node("api_node", run_api_agent)
graph.add_node("sql_node", run_sql_agent)

# Define edges: Always start with API agent
graph.add_edge(START, "api_node")

# After API agent, decide whether to fallback to SQL agent or end
graph.add_conditional_edges(
    "api_node", 
    should_fallback_to_sql, 
    {
        "sql_node": "sql_node",
        "__end__": END
    }
)

# SQL agent always ends after processing
graph.add_edge("sql_node", END)

meta_agent = graph.compile()

# --- 6. Example Usage ---
if __name__ == "__main__":
    # Interactive loop example
    context = create_initial_context(user_id=1)

    print("=== Sequential Agent System (API -> SQL Fallback) ===")
    print("The system will first try the API agent.")
    print("If API agent cannot fulfill the request, it will automatically route to SQL agent.")
    print("Type '/exit' to quit\n")

    while True:
        user_input = input("You: ")
        if user_input.strip().lower() == "/exit":
            break

        # Reset fallback flags for new request
        context["messages"].append(HumanMessage(content=user_input))
        context["api_agent_attempted"] = False
        context["needs_sql_fallback"] = False
        
        result = meta_agent.invoke(context)
        context = result

        print("\nAgent Response:")
        # Show the last response message
        for m in context["messages"][-1:]:
            m.pretty_print()
        print(f"\n[System] Last agent used: {context.get('last_agent_used', 'none')}\n")
