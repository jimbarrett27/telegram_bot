"""AI meme generator — picks the best template and writes the text."""

import logging
from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from agents import Agent
from agents.config import get_llm
from agents.utils import content_to_str
from memes.renderer import load_metadata, render_meme

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a meme generator. Given a topic or prompt, pick the single best \
meme template and fill in the text to make it funny.

Rules:
- Keep text SHORT — memes work best with punchy, concise text.
- Match the joke structure to the template (read the tool descriptions carefully).
- Use exactly one tool call. Do not explain yourself, just make the meme.
"""

DEFAULT_MODEL = "google/gemini-2.5-flash"


def _build_tools() -> list[StructuredTool]:
    """Build one LangChain tool per meme template from metadata."""
    metadata = load_metadata()
    tools = []

    for template_name, template in metadata.items():
        description = template.get("description", f"Generate a {template_name} meme.")
        labels = [box["label"] for box in template["text_boxes"]]

        # Build a Pydantic model with one string field per text box label
        field_definitions = {
            label: (str, Field(description=f"Text for the '{label}' region"))
            for label in labels
        }
        ArgsModel = create_model(f"{template_name}_args", **field_definitions)

        # Capture template_name in closure
        def _make_fn(tpl_name: str):
            def _render(**kwargs: str) -> str:
                img_bytes = render_meme(tpl_name, kwargs)
                # Store the bytes on the function so the caller can retrieve them
                _render._last_result = img_bytes
                return f"Rendered {tpl_name} meme ({len(img_bytes)} bytes)"
            return _render

        fn = _make_fn(template_name)

        tool = StructuredTool.from_function(
            func=fn,
            name=template_name,
            description=description,
            args_schema=ArgsModel,
        )
        tools.append(tool)

    return tools


def generate_meme(
    prompt: str,
    model: str = DEFAULT_MODEL,
    provider: str = "openrouter",
) -> tuple[bytes, str]:
    """Generate a meme from a text prompt.

    Args:
        prompt: Topic or description for the meme.
        model: LLM model to use.
        provider: LLM provider.

    Returns:
        (png_bytes, template_name) tuple.
    """
    tools = _build_tools()
    llm = get_llm(provider=provider, model=model, temperature=1.0)

    agent = Agent(
        name="meme_generator",
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
        llm=llm,
    )

    result = agent.invoke([HumanMessage(content=prompt)])

    # Find which tool was called and get the rendered bytes
    for msg in result["messages"]:
        if msg.type == "tool":
            # Find the matching tool function to get the stored result
            for tool in tools:
                if tool.name == msg.name and hasattr(tool.func, "_last_result"):
                    return tool.func._last_result, tool.name

    raise RuntimeError("Agent did not produce a meme — no tool was called")
