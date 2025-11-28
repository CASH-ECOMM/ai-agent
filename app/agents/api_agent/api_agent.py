from langgraph.graph import MessagesState
from langchain.messages import SystemMessage, HumanMessage, ToolMessage
from ...tools import tools
import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from typing import Literal
from langgraph.graph import END, START, MessagesState, StateGraph
from langchain_core.runnables.graph import CurveStyle, MermaidDrawMethod, NodeStyles

load_dotenv()

model = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4.1-nano-2025-04-14"))

tools_by_name = {tool.name: tool for tool in tools}
llm_with_tools = model.bind_tools(tools)


def llm_call(state: MessagesState):
    """LLM decides whether to call a tool or not"""

    system_prompt = """
      You are an AI assistant for an auction e-commerce system. 
      Your goal is to help users interact with the system by answering questions, performing searches and other actions related to the user's needs. 
      Only reference the tools available to you.
      
      IMPORTANT WORKFLOWS:
      1. When creating a new item for auction:
         - First, ask the user for item details (title, description, starting price, duration)
         - After user confirms, call create_catalogue_item to create the item
         - IMMEDIATELY after creating the item, call start_auction with the catalogue_id from the response to start the auction
         - Inform the user that both the item has been created AND the auction has been started
      
      2. Before performing any action that changes the system (create, bid, start auction):
         - Always ask the user for confirmation first
         - Provide a clear summary of what will happen
      
      3. Data integrity:
         - Never make up information or provide false details
         - Always use the tools available to fetch real data from the system
         - Never disclose other users' information or data
      """

    return {
        "messages": [
            llm_with_tools.invoke(
                [SystemMessage(content=(system_prompt))] + state["messages"]  # type: ignore
            )
        ]
    }


def tool_node(state: dict):
    """Performs the tool call"""

    result = []
    last_message = state["messages"][-1]
    for tool_call in last_message.tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}


# Conditional edge function to route to the tool node or end based upon whether the LLM made a tool call
def should_continue(state: MessagesState) -> Literal["tool_node", END]:  # type: ignore
    """Decide if we should continue the loop or stop based upon whether the LLM made a tool call"""

    messages = state["messages"]
    last_message = messages[-1]

    # If the LLM makes a tool call, then perform an action
    if last_message.tool_calls:  # type: ignore
        return "tool_node"

    # Otherwise, we stop (reply to the user)
    return END


# Build workflow
graph = StateGraph(MessagesState)
graph.add_node("llm_call", llm_call)
graph.add_node("tool_node", tool_node)  # type: ignore
graph.add_edge(START, "llm_call")
graph.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
graph.add_edge("tool_node", "llm_call")
agent = graph.compile()

# Show the agent
# with open("api_agent_graph.png", "wb") as f:
#     f.write(agent.get_graph().draw_mermaid_png())

# Test the agent in a loop
# messages = []
# while True:
#     user_input = input("You: ")
#     if user_input.strip().lower() == "/exit":
#         break
#     messages.append(HumanMessage(content=user_input))
#     result = agent.invoke({"messages": messages})
#     messages = result["messages"]
#     for m in messages[-1:]:
#         m.pretty_print()
