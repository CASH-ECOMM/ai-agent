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
from pydantic import BaseModel, Field

# tracer_provider = register(project_name="Supervisor Agent V2", auto_instrument=True)


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


class APIAgentDecision(BaseModel):
    """Structured output from API agent to determine if request can be fulfilled."""

    can_handle_request: bool = Field(
        description="Whether the API agent can handle this request with available tools. True if: 1) performing an action, 2) asking follow-up questions to complete a task, 3) providing information from tools. False ONLY if the request requires database analytics/queries that tools cannot provide."
    )
    response: str = Field(description="The agent's response to the user")
    reasoning: str = Field(
        description="Brief explanation of why the request can or cannot be handled"
    )


def run_api_agent(state: ConversationContext):
    """Run the API agent first to attempt fulfilling the request."""
    from app.agents.api_agent.tools import jwt_token_context

    # Extract the last user message
    user_input = state["messages"][-1].content if state["messages"] else ""

    print(f"\n[API Agent] Processing request: {user_input[:50]}...")

    try:
        # Set JWT token in context for API tools to use
        jwt_token = state["metadata"].get("jwt_token", "")
        jwt_token_context.set(jwt_token)

        # Create a structured LLM that wraps the API agent with decision-making
        structured_llm = model.with_structured_output(APIAgentDecision)

        # Combine API agent invocation with decision-making in a single prompt
        agent_system_prompt = f"""
        You are evaluating whether an API agent can HANDLE a user request (not necessarily fulfill it completely).
        
        The API agent CAN HANDLE requests when:
        - It has tools to perform the requested action (posting items, bidding, etc.)
        - It's having a conversation to gather necessary information (asking for details)
        - It's providing information from available tools
        - It's guiding the user through a multi-step process
        
        The API agent CANNOT HANDLE requests when:
        - The request requires database queries/analytics that tools don't provide
        - The request asks for statistics, trends, or historical analysis
        - The request needs data aggregation across multiple records
        - The request asks "what is the most/least/average..." type questions
        
        Key distinction: Asking follow-up questions to complete a task = CAN HANDLE
        Lacking the tools entirely = CANNOT HANDLE
        """

        # Invoke API agent to get its response
        result = api_agent.invoke({"messages": state["messages"]})
        state["messages"] = result["messages"]

        last_message = state["messages"][-1]
        agent_response = (
            last_message.content
            if hasattr(last_message, "content")
            else str(last_message)
        )

        # Single LLM call with structured output for both response and decision
        decision_prompt = f"""
        User Request: {user_input}
        API Agent Response: {agent_response}
        
        Question: Is the API agent actively HANDLING this request?
        
        Consider it as HANDLING if:
        - The agent is asking for more details to complete the task
        - The agent is performing or offering to perform an action
        - The agent is engaged in a conversation toward completing the request
        
        Consider it as NOT HANDLING only if:
        - The agent explicitly states it lacks the capability
        - The request requires database analytics/queries the agent cannot do
        - The agent says it doesn't have access to the needed data
        """

        decision = structured_llm.invoke(
            [
                SystemMessage(content=agent_system_prompt),
                HumanMessage(content=decision_prompt),
            ]
        )

        state["last_agent_used"] = "api_agent"
        state["api_agent_attempted"] = True

        print(f"[API Agent] Decision - Can handle: {decision.can_handle_request}")
        print(f"[API Agent] Reasoning: {decision.reasoning}")

        # Set fallback flag based on structured decision
        state["needs_sql_fallback"] = not decision.can_handle_request

        if state["needs_sql_fallback"]:
            print("[API Agent] Cannot handle request, will route to SQL agent")

        return state
    except Exception as e:
        print(f"[API Agent] Error: {str(e)}, will route to SQL agent")
        state["api_agent_attempted"] = True
        state["needs_sql_fallback"] = True
        state["messages"].append(
            AIMessage(
                content=f"API agent encountered an error. Routing to SQL agent for assistance."
            )
        )
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
            state["messages"].append(
                AIMessage(content=f"SQL query error: {sql_result['error']}")
            )
            print(f"[SQL Agent] Error: {sql_result['error']}")
        else:
            state["messages"].append(
                AIMessage(content="SQL agent completed but no results were returned.")
            )

        state["last_agent_used"] = "sql_agent"
    except Exception as e:
        print(f"[SQL Agent] Error: {str(e)}")
        state["messages"].append(
            AIMessage(content=f"SQL agent encountered an error: {str(e)}")
        )

    return state


# --- 4. Conditional routing function ---
def should_fallback_to_sql(
    state: ConversationContext,
) -> Literal["sql_node", "__end__"]:
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
    "api_node", should_fallback_to_sql, {"sql_node": "sql_node", "__end__": END}
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
    print(
        "If API agent cannot fulfill the request, it will automatically route to SQL agent."
    )
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
