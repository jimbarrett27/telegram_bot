import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dnd.dice import resolve_check, RollResult
from llm.llm_util import get_llm_response

_PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass
class PlayerContext:
    name: str
    character_class: str = "Adventurer"
    character_description: Optional[str] = None


@dataclass
class ResolvedAction:
    player_name: str
    text: str
    outcome: str


@dataclass
class EncounterContext:
    name: str
    description: str
    skill: Optional[str] = None
    dc: Optional[int] = None


@dataclass
class NpcContext:
    name: str
    description: str
    motivation: Optional[str] = None


@dataclass
class NarratorContext:
    """Adventure and scene context passed to the narrator."""
    narrator_context: str = (
        "You are narrating a classic fantasy adventure in a world of swords, magic, and ancient mysteries. "
        "The tone is dramatic but not overly dark. Heroes can triumph, villains have motives, and the world reacts to player choices."
    )
    adventure_name: str = "The Adventure"
    adventure_description: str = "A group of adventurers sets out to face unknown dangers."
    scene_name: str = "The Journey"
    scene_description: str = "The adventurers find themselves at a pivotal moment."
    encounters: list[EncounterContext] = field(default_factory=list)
    npcs: list[NpcContext] = field(default_factory=list)
    available_skills: str = "Athletics, Perception, Persuasion, Stealth, Arcana, Investigation"


def _parse_json_response(text: str) -> dict:
    """Extract the first JSON object from an LLM response, stripping markdown fences."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in LLM response: {text!r}")
    return json.loads(match.group())


class Narrator:
    def __init__(self, context: Optional[NarratorContext] = None):
        self.context = context or NarratorContext()

    async def narrate_scene(
        self,
        players: list[PlayerContext],
        story_so_far: Optional[str] = None,
    ) -> str:
        ctx = self.context
        params = {
            "narrator_context": ctx.narrator_context,
            "adventure_name": ctx.adventure_name,
            "adventure_description": ctx.adventure_description,
            "scene_name": ctx.scene_name,
            "scene_description": ctx.scene_description,
            "encounters": [
                {"name": e.name, "description": e.description, "skill": e.skill, "dc": e.dc}
                for e in ctx.encounters
            ],
            "npcs": [
                {"name": n.name, "description": n.description, "motivation": n.motivation}
                for n in ctx.npcs
            ],
            "players": [
                {
                    "name": p.name,
                    "character_class": p.character_class,
                    "character_description": p.character_description or "No description.",
                }
                for p in players
            ],
            "story_so_far": story_so_far or "",
        }
        return await asyncio.to_thread(
            get_llm_response, str(_PROMPTS_DIR / "narrate_scene.jinja2"), params
        )

    async def evaluate_and_resolve_action(
        self,
        player: PlayerContext,
        scene_narrative: str,
        action_text: str,
        recent_actions: Optional[list[ResolvedAction]] = None,
    ) -> tuple[str, Optional[RollResult]]:
        """Evaluate a player action and narrate the outcome.

        Returns (outcome_narration, roll_result_or_None).
        """
        ctx = self.context
        recent = recent_actions or []

        eval_params = {
            "narrator_context": ctx.narrator_context,
            "scene_name": ctx.scene_name,
            "scene_description": ctx.scene_description,
            "encounters": [
                {"name": e.name, "description": e.description, "skill": e.skill, "dc": e.dc}
                for e in ctx.encounters
            ],
            "npcs": [
                {"name": n.name, "description": n.description, "motivation": n.motivation}
                for n in ctx.npcs
            ],
            "player_name": player.name,
            "player_class": player.character_class,
            "player_skills": "",
            "player_inventory": "",
            "scene_narrative": scene_narrative,
            "recent_actions": [
                {"player_name": a.player_name, "text": a.text, "outcome": a.outcome}
                for a in recent
            ],
            "action_text": action_text,
            "available_skills": ctx.available_skills,
        }

        eval_text = await asyncio.to_thread(
            get_llm_response, str(_PROMPTS_DIR / "evaluate_action.jinja2"), eval_params
        )
        evaluation = _parse_json_response(eval_text)

        requires_check = evaluation.get("requires_check", False)
        pre_roll_narration = evaluation.get("narration", "")

        # Narrative actions are fully resolved by the evaluate step
        if not requires_check:
            return pre_roll_narration, None

        skill = evaluation.get("skill", "Athletics")
        dc = int(evaluation.get("dc", 12))
        roll_result = resolve_check(dc=dc, skill_name=skill)

        resolve_params = {
            "narrator_context": ctx.narrator_context,
            "scene_name": ctx.scene_name,
            "scene_description": ctx.scene_description,
            "npcs": [
                {"name": n.name, "description": n.description, "motivation": n.motivation}
                for n in ctx.npcs
            ],
            "player_name": player.name,
            "player_class": player.character_class,
            "scene_narrative": scene_narrative,
            "recent_actions": [
                {"player_name": a.player_name, "text": a.text, "outcome": a.outcome}
                for a in recent
            ],
            "action_text": action_text,
            "pre_roll_narration": pre_roll_narration,
            "skill_check": {
                "skill": roll_result.skill_name,
                "dc": roll_result.dc,
                "roll": roll_result.roll,
                "modifier": roll_result.modifier,
                "total": roll_result.total,
                "success": roll_result.success,
            },
        }

        resolve_text = await asyncio.to_thread(
            get_llm_response, str(_PROMPTS_DIR / "resolve_action.jinja2"), resolve_params
        )
        resolution = _parse_json_response(resolve_text)
        outcome = resolution.get("narration", resolve_text)

        return outcome, roll_result
