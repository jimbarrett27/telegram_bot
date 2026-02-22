"""
Base agent class that encapsulates a ReAct-style subgraph.

Adapted from the SignalAgents project for the D&D game system.
"""

import logging
from typing import Annotated, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


class Agent:
    """
    A self-contained agent with its own ReAct subgraph.

    The subgraph runs a standard loop: the LLM reasons about the current
    messages, optionally calls tools, and loops until it produces a final
    response with no tool calls.
    """

    def __init__(
        self,
        name: str,
        system_prompt: str,
        tools: list,
        llm: BaseChatModel,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = list(tools)
        self._base_llm = llm
        self.llm = llm.bind_tools(tools) if tools else llm
        self.graph = self._build_graph()

    def _reason(self, state: AgentState) -> dict:
        messages = [SystemMessage(content=self.system_prompt)] + state["messages"]
        logger.debug("Agent '%s' reasoning with %d messages", self.name, len(messages))
        response = self.llm.invoke(messages)

        if hasattr(response, "tool_calls") and response.tool_calls:
            for tc in response.tool_calls:
                logger.info("Agent '%s' calling tool: %s", self.name, tc["name"])
                logger.debug("Agent '%s' tool args for %s: %s", self.name, tc["name"], tc["args"])
        else:
            text = response.content or ""
            logger.debug("Agent '%s' produced final response (%d chars)", self.name, len(text))

        return {"messages": [response]}

    def _build_graph(self):
        builder = StateGraph(AgentState)
        builder.add_node("reason", self._reason)
        builder.set_entry_point("reason")

        if self.tools:
            tool_node = ToolNode(self.tools)
            agent = self

            def _execute_tools(state: AgentState) -> dict:
                result = tool_node.invoke(state)
                for msg in result.get("messages", []):
                    name = getattr(msg, "name", "unknown")
                    content = str(msg.content) if msg.content else ""
                    logger.debug(
                        "Agent '%s' tool result from %s (%d chars): %.500s",
                        agent.name, name, len(content), content,
                    )
                return result

            builder.add_node("tools", _execute_tools)
            builder.add_conditional_edges("reason", tools_condition)
            builder.add_edge("tools", "reason")
        else:
            builder.add_edge("reason", END)

        return builder.compile()

    def invoke(self, messages: list[AnyMessage]) -> AgentState:
        logger.info("Invoking agent: %s", self.name)
        result = self.graph.invoke({"messages": messages})
        logger.info("Agent '%s' finished", self.name)
        return result

    def get_response_text(self, messages: list[AnyMessage]) -> str:
        """Invoke the agent and extract the final text response."""
        result = self.invoke(messages)
        for msg in reversed(result["messages"]):
            if msg.type == "ai" and msg.content:
                content = msg.content
                if isinstance(content, list):
                    text_parts = [
                        part.get("text", "")
                        for part in content
                        if isinstance(part, dict) and "text" in part
                    ]
                    return "".join(text_parts)
                return content
        return "The Dungeon Master is silent..."

    def __repr__(self) -> str:
        tool_names = [t.name for t in self.tools]
        return f"Agent(name={self.name!r}, tools={tool_names})"
