# import os
# import logging
# from typing import Literal
# from langchain_openai import ChatOpenAI
# from langchain.messages import SystemMessage, HumanMessage, ToolMessage
# from langgraph.graph import END, START, MessagesState, StateGraph
# from .tools import tools, query_database, manage_api_operations
# from dotenv import load_dotenv

# load_dotenv()

# logging.basicConfig(
#     level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
# )
# logger = logging.getLogger(__name__)

# model = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o-mini"))
# llm_with_tools = model.bind_tools(tools)

# sessions: dict[str, int] = {}


# def supervisor_call(state: MessagesState):
#     SUPERVISOR_PROMPT = """
#     You are a helpful AI assistant for an auction e-commerce system.

#     You coordinate between two specialized agents:
#     1. **Database Query Agent** - For searching, analyzing, and retrieving data
#     2. **API Operations Agent** - For creating, updating, or modifying system data

#     Your responsibilities:
#     - Understand user requests and route them to the appropriate agent
#     - Use the database agent for READ operations (queries, searches, analytics)
#     - Use the API agent for WRITE operations (create, update, delete actions)
#     - When a request requires both operations, coordinate between agents
#     - Always maintain user context and security (user_id)
#     - Provide clear, helpful responses based on agent results

#     Guidelines:
#     - For questions about "what", "how many", "show me", "list" → use query_database
#     - For actions like "create", "update", "delete", "place bid" → use manage_api_operations
#     - If unsure, prefer query_database for safety (read-only operations)
#     - Never make up information - always use the tools available
#     - Respect user privacy and security constraints

#     When routing requests:
#     - Database queries: statistics, reports, searching historical data, filtering
#     - API operations: creating items, placing bids, updating records, real-time actions
#     """

#     return {
#         "messages": [
#             llm_with_tools.invoke(
#                 [SystemMessage(content=SUPERVISOR_PROMPT)] + state["messages"]  # type: ignore
#             )
#         ]
#     }


# def tool_node(state: MessagesState):
#     """Execute the selected tool."""
#     result_messages = []
#     last_message = state["messages"][-1]

#     for tool_call in last_message.tool_calls:
#         tool_name = tool_call["name"]
#         tool_args = tool_call["args"]

#         logger.info(f"Executing tool: {tool_name} with args: {tool_args}")

#         if tool_name == "query_database":
#             result = query_database.invoke(tool_args)
#             result_messages.append(
#                 ToolMessage(content=result, tool_call_id=tool_call["id"])
#             )
#         elif tool_name == "manage_api_operations":
#             result = manage_api_operations.invoke(tool_args)
#             result_messages.append(
#                 ToolMessage(content=result, tool_call_id=tool_call["id"])
#             )

#     return {"messages": result_messages}


# def should_continue(state: MessagesState) -> Literal["tool_node", "__end__"]:
#     """Decide if we should continue the loop or stop."""

#     messages = state["messages"]
#     last_message = messages[-1]

#     if last_message.tool_calls:
#         return "tool_node"
#     return END


# graph = StateGraph(MessagesState)
# graph.add_node("supervisor_call", supervisor_call)
# graph.add_node("tool_node", tool_node)
# graph.add_edge(START, "supervisor_call")
# graph.add_conditional_edges(
#     "supervisor_call", should_continue, {"tool_node": "tool_node", "__end__": END}
# )
# graph.add_edge("tool_node", "supervisor_call")

# supervisor_agent = graph.compile()


# # Test the agent in a loop
# messages = []
# while True:
#     user_input = input("You: ")
#     if user_input.strip().lower() == "/exit":
#         break
#     messages.append(HumanMessage(content=user_input))  # Append to end, not prepend
#     result = supervisor_agent.invoke({"messages": messages})
#     messages = result["messages"]
#     for m in messages[-1:]:
#         m.pretty_print()
