from langgraph.graph import MessagesState
from langchain.messages import SystemMessage, HumanMessage, ToolMessage
from .tools import tools
import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from typing import Literal
from IPython.display import Image, display
from langgraph.graph import END, START, MessagesState, StateGraph
from langchain_core.runnables.graph import CurveStyle, MermaidDrawMethod, NodeStyles

load_dotenv()

model = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4.1-mini-2025-04-14"))

tools_by_name = {tool.name: tool for tool in tools}
llm_with_tools = model.bind_tools(tools)


def llm_call(state: MessagesState):
    """LLM decides whether to call a tool or not"""

    return {
        "messages": [
            llm_with_tools.invoke(
                [
                    SystemMessage(
                        content=(
                            "You are an AI assistant for an auction e-commerce system. Your goal is to help users interact with the system by answering questions, performing searches and other actions related to the user's needs. Only reference the tools available to you. Under no circumstances should you make up information or provide false details. Always use the tools available to you to fetch real data from the system. You must never use or disclose other user's information or data."
                        )
                    )
                ]
                + state["messages"]
            )
        ]
    }


def tool_node(state: dict):
    """Performs the tool call"""

    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}


# Conditional edge function to route to the tool node or end based upon whether the LLM made a tool call
def should_continue(state: MessagesState) -> Literal["tool_node", END]:
    """Decide if we should continue the loop or stop based upon whether the LLM made a tool call"""

    messages = state["messages"]
    last_message = messages[-1]

    # If the LLM makes a tool call, then perform an action
    if last_message.tool_calls:
        return "tool_node"

    # Otherwise, we stop (reply to the user)
    return END


# Build workflow
agent_builder = StateGraph(MessagesState)

# Add nodes
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)

# Add edges to connect nodes
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
agent_builder.add_edge("tool_node", "llm_call")

# Compile the agent
agent = agent_builder.compile()

# Show the agent
# with open("api_agent_graph.png", "wb") as f:
#     f.write(agent.get_graph().draw_mermaid_png())

# Invoke
messages = []
while True:
    user_input = input("You: ")
    if user_input.strip().lower() == "/exit":
        break
    messages.append(HumanMessage(content=user_input))
    result = agent.invoke({"messages": messages})
    messages = result["messages"]
    for m in messages[-1:]:
        m.pretty_print()
