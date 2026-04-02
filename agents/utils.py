"""Shared utility functions used across agents and tools."""


def content_to_str(content) -> str:
    """Normalize LLM message content to a plain string (text blocks only).

    Some models return content as a list of content blocks
    (e.g. [{'type': 'text', 'text': '...'}, {'type': 'thinking', ...}])
    instead of a plain string. This extracts only the text blocks.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
            if not isinstance(block, dict) or block.get("type") != "thinking"
        )
    return str(content) if content else ""
