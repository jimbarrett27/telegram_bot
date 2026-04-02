"""Base agent class that encapsulates a ReAct-style subgraph."""

import logging
from collections.abc import Callable
from typing import Annotated, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool as tool_decorator
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from agents.utils import content_to_str

logger = logging.getLogger(__name__)

# Keep module-level alias for internal use
_content_to_str = content_to_str


def _extract_thinking(content) -> str | None:
    """Extract thinking/reasoning blocks from LLM content.

    Returns the concatenated thinking text, or None if no thinking blocks.
    """
    if not isinstance(content, list):
        return None
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "thinking":
            thinking = block.get("thinking", "")
            if thinking:
                parts.append(thinking)
    return "\n".join(parts) if parts else None

# Callback type: (agent_name, event_kind, data_dict)
AgentEventCallback = Callable[[str, str, dict], None]


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
        description: str = "",
        recursion_limit: int = 500,
    ):
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.tools = list(tools)
        self._base_llm = llm
        self.llm = llm.bind_tools(tools) if tools else llm
        self._on_event: AgentEventCallback | None = None
        self.recursion_limit = recursion_limit
        self.graph = self._build_graph()

    def _emit(self, kind: str, data: dict) -> None:
        if self._on_event:
            try:
                self._on_event(self.name, kind, data)
            except Exception:
                logger.debug("Agent '%s' event callback error", self.name, exc_info=True)

    def _reason(self, state: AgentState) -> dict:
        messages = [SystemMessage(content=self.system_prompt)] + state["messages"]
        logger.debug("Agent '%s' reasoning with %d messages", self.name, len(messages))
        logger.debug("Agent '%s' system prompt: %s", self.name, self.system_prompt[:200])
        self._emit("reasoning", {"num_messages": len(messages)})
        response = self.llm.invoke(messages)

        # Check for max_tokens truncation
        finish_reason = response.response_metadata.get("finish_reason", "")
        if finish_reason == "length":
            logger.warning(
                "Agent '%s' hit max_tokens (finish_reason=length) with %d messages",
                self.name, len(messages),
            )
            self._emit("length_warning", {
                "finish_reason": "length",
                "num_messages": len(messages),
            })
            # Retry once with trimmed history: keep system prompt + last N exchanges
            keep_recent = 6  # last 6 non-system messages
            trimmed = [messages[0]] + messages[-keep_recent:]
            logger.info(
                "Agent '%s' retrying with trimmed history (%d -> %d messages)",
                self.name, len(messages), len(trimmed),
            )
            response = self.llm.invoke(trimmed)
            finish_reason = response.response_metadata.get("finish_reason", "")
            if finish_reason == "length":
                logger.warning(
                    "Agent '%s' hit max_tokens again after retry — proceeding with truncated response",
                    self.name,
                )

        # Emit thinking blocks (chain-of-thought summaries)
        thinking = _extract_thinking(response.content)
        if thinking:
            logger.info("Agent '%s' thinking (%d chars): %.500s", self.name, len(thinking), thinking)
            self._emit("thinking", {"text": thinking})

        # Emit the LLM's text content — present even alongside tool calls
        # when the model explains its plan before acting
        text = _content_to_str(response.content)
        if hasattr(response, "tool_calls") and response.tool_calls:
            if text:
                self._emit("llm_text", {"text": text})
            for tc in response.tool_calls:
                logger.info("Agent '%s' calling tool: %s", self.name, tc["name"])
                logger.debug("Agent '%s' tool call args for %s: %s", self.name, tc["name"], tc["args"])
                self._emit("tool_call", {"tool": tc["name"], "args": tc["args"]})
        else:
            logger.debug("Agent '%s' produced final response (%d chars)", self.name, len(text))
            self._emit("response", {"text": text, "finish_reason": finish_reason})
        return {"messages": [response]}

    def _build_graph(self):
        builder = StateGraph(AgentState)
        builder.add_node("reason", self._reason)
        builder.set_entry_point("reason")

        if self.tools:
            tool_node = ToolNode(self.tools)
            agent = self  # capture for closure

            def _execute_tools(state: AgentState) -> dict:
                result = tool_node.invoke(state)
                for msg in result.get("messages", []):
                    name = getattr(msg, "name", "unknown")
                    content = _content_to_str(msg.content)
                    logger.debug("Agent '%s' tool result from %s (%d chars): %.500s",
                                 agent.name, name, len(content), content)
                    agent._emit("tool_result", {
                        "tool": name,
                        "content": content,
                    })
                return result

            builder.add_node("tools", _execute_tools)
            builder.add_conditional_edges("reason", tools_condition)
            builder.add_edge("tools", "reason")
        else:
            builder.add_edge("reason", END)

        return builder.compile()

    def invoke(self, messages: list[AnyMessage]) -> AgentState:
        logger.info("Invoking agent: %s", self.name)
        logger.debug("Agent '%s' input messages: %s", self.name, [_content_to_str(m.content)[:200] if hasattr(m, 'content') and m.content else str(m) for m in messages])
        result = self.graph.invoke(
            {"messages": messages},
            {"recursion_limit": self.recursion_limit},
        )
        logger.info("Agent '%s' finished", self.name)
        return result

    def set_on_event(
        self,
        callback: AgentEventCallback | None,
        propagate_to_subagents: bool = False,
    ) -> None:
        """Set a callback for agent events (tool_call, tool_result, etc.)."""
        self._on_event = callback
        if not propagate_to_subagents:
            return
        for t in self.tools:
            sub: Agent | None = getattr(t, "_sub_agent", None)
            if sub is None:
                continue
            if callback is None:
                sub.set_on_event(None)
            else:
                parent_name = self.name
                sub_name = sub.name

                def _wrap(
                    agent_name: str,
                    kind: str,
                    data: dict,
                    _pn: str = parent_name,
                    _sn: str = sub_name,
                    _cb: AgentEventCallback = callback,
                ) -> None:
                    _cb(_pn, kind, {**data, "sub_agent": _sn})

                sub.set_on_event(_wrap)

    def add_tools(self, new_tools: list):
        """Add tools to this agent, rebinding the LLM and rebuilding the graph."""
        self.tools.extend(new_tools)
        self.llm = self._base_llm.bind_tools(self.tools)
        self.graph = self._build_graph()

    def as_tool(self, description: str):
        """Create a LangChain tool that invokes this agent with a query string."""
        agent = self

        @tool_decorator(agent.name, description=description)
        def _invoke(query: str) -> str:
            logger.info("Agent-as-tool invoked: %s", agent.name)
            logger.debug("Agent-as-tool '%s' query: %s", agent.name, query[:500])
            result = agent.invoke([HumanMessage(content=query)])
            for msg in reversed(result["messages"]):
                if msg.type == "ai" and msg.content:
                    return _content_to_str(msg.content)
            return "No response from agent"

        # Stash reference so parent.set_on_event() can find us
        object.__setattr__(_invoke, "_sub_agent", agent)
        return _invoke

    def __repr__(self) -> str:
        tool_names = [t.name for t in self.tools]
        return f"Agent(name={self.name!r}, tools={tool_names})"
