"""Unit tests for the panel retry loop (the LLM itself is stubbed out)."""

import json

import pytest

from tapestry import generator
from tapestry.svg import PANEL_HEIGHT, PANEL_WIDTH

STORIES = [
    {"title": f"Story {i}", "summary": f"Summary {i}", "link": f"https://example.com/{i}"}
    for i in range(generator.STORIES_PER_PANEL)
]

# Enough drawable elements to clear the "truncated or near-empty" check.
VALID_SVG = (
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{PANEL_WIDTH}" '
    f'height="{PANEL_HEIGHT}" viewBox="0 0 {PANEL_WIDTH} {PANEL_HEIGHT}">'
    '<rect x="0" y="40" width="1600" height="160" fill="#d9c9a3"/>'
    + "".join(
        f'<circle cx="{100 * i}" cy="120" r="20" fill="#8b5a2b"/>' for i in range(10)
    )
    + "</svg>"
)


def replies(monkeypatch, *outcomes):
    """Stub the LLM with one outcome per call; exceptions are raised, str returned.

    Returns the list of ``problem`` values the prompt was rendered with, so a test
    can assert what (if anything) was fed back into each retry.
    """
    seen_problems = []
    remaining = list(outcomes)

    def fake_get_llm_response(template_path, params, model):
        seen_problems.append(params["problem"])
        outcome = remaining.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(generator, "get_llm_response", fake_get_llm_response)
    return seen_problems


def test_api_failure_costs_one_attempt_not_the_whole_run(monkeypatch):
    """The bug that lost 2026-07-22: OpenRouter returned a body that wasn't JSON.

    The call to the model used to sit outside the retry loop's try block, so one
    flaky response aborted all three attempts and the day went un-drawn.
    """
    api_error = json.JSONDecodeError("Expecting value", "\n" * 1386, 7623)
    seen = replies(monkeypatch, api_error, VALID_SVG)

    panel = generator.generate_panel(STORIES)

    assert panel.svg.startswith("<svg")
    assert len(seen) == 2


def test_api_failure_is_not_fed_back_as_a_prompt_problem(monkeypatch):
    # There's no model output to critique, so the retry must be asked afresh
    # rather than told to "fix" an error the model never saw.
    seen = replies(monkeypatch, ConnectionError("upstream stalled"), VALID_SVG)

    generator.generate_panel(STORIES)

    assert seen == [None, None]


def test_invalid_svg_is_fed_back_into_the_retry(monkeypatch):
    seen = replies(monkeypatch, "not markup at all", VALID_SVG)

    generator.generate_panel(STORIES)

    assert seen[0] is None
    assert seen[1], "the retry should be told what was wrong with attempt 1"


def test_gives_up_after_max_attempts_and_reports_the_last_failure(monkeypatch):
    seen = replies(monkeypatch, *[ConnectionError("upstream stalled")] * 3)

    with pytest.raises(RuntimeError, match="upstream stalled"):
        generator.generate_panel(STORIES, max_attempts=3)

    assert len(seen) == 3
