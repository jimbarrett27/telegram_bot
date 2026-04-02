"""AI meme generator — picks the best template and writes the text."""

import logging

from langchain_core.messages import HumanMessage

from agents import Agent
from agents.config import get_llm
from memes import tools as meme_tools

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


def generate_meme(
    prompt: str,
    model: str = DEFAULT_MODEL,
    provider: str = "openrouter",
) -> tuple[bytes, str]:
    """Generate a meme from a text prompt.

    Returns:
        (png_bytes, template_name) tuple.
    """
    meme_tools.last_render = None

    llm = get_llm(provider=provider, model=model, temperature=1.0)
    agent = Agent(
        name="meme_generator",
        system_prompt=SYSTEM_PROMPT,
        tools=meme_tools.ALL_TOOLS,
        llm=llm,
    )

    agent.invoke([HumanMessage(content=prompt)])

    if meme_tools.last_render is None:
        raise RuntimeError("Agent did not produce a meme — no tool was called")

    return meme_tools.last_render
