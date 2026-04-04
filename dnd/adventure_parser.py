"""Parse adventure markdown files into structured data for loading into the database.

Expected format:

    # Adventure Title

    Description paragraph(s).

    ## Setting

    Setting context for the narrator.

    ## NPCs

    ### NPC Name
    Description of the NPC.
    **Motivation:** What drives this NPC.

    ## Scenes

    ### Scene Name
    Description of the scene.

    #### Encounters
    - **Encounter Name** — Description. *SkillName DC 15*
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedEncounter:
    name: str
    description: str
    skill: str | None = None
    dc: int | None = None


@dataclass
class ParsedNPC:
    name: str
    description: str
    motivation: str | None = None


@dataclass
class ParsedScene:
    name: str
    description: str
    encounters: list[ParsedEncounter] = field(default_factory=list)


@dataclass
class ParsedAdventure:
    name: str
    description: str
    narrator_context: str
    setting: str | None = None
    npcs: list[ParsedNPC] = field(default_factory=list)
    scenes: list[ParsedScene] = field(default_factory=list)


class AdventureParseError(Exception):
    pass


_ENCOUNTER_RE = re.compile(
    r"^\-\s+\*\*(.+?)\*\*\s*[—–-]\s*(.+?)\s*\*(.+?)\s+DC\s+(\d+)\*\s*$"
)
_ENCOUNTER_NO_SKILL_RE = re.compile(
    r"^\-\s+\*\*(.+?)\*\*\s*[—–-]\s*(.+)$"
)


def parse_adventure(text: str) -> ParsedAdventure:
    lines = text.strip().split("\n")

    # Extract title from first H1
    title = None
    content_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:].strip()
            content_start = i + 1
            break

    if not title:
        raise AdventureParseError("Missing adventure title (# Title)")

    # Split into sections by H2
    sections: dict[str, list[str]] = {}
    current_section = "_preamble"
    sections[current_section] = []

    for line in lines[content_start:]:
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("### "):
            current_section = stripped[3:].strip().lower()
            sections[current_section] = []
        else:
            sections[current_section].append(line)

    # Description and setting from preamble
    setting_ref = None
    preamble_lines = []
    for line in sections.get("_preamble", []):
        stripped = line.strip()
        if stripped.lower().startswith("**setting:**"):
            setting_ref = stripped.split(":**", 1)[1].strip()
        else:
            preamble_lines.append(line)

    description = _join_lines(preamble_lines)
    if not description:
        raise AdventureParseError("Missing adventure description (text after title, before first ## section)")

    # Narrator context (## Setting section in the markdown)
    narrator_context = _join_lines(sections.get("setting", []))
    if not narrator_context:
        raise AdventureParseError("Missing ## Setting section")

    # NPCs
    npcs = _parse_npcs(sections.get("npcs", []))

    # Scenes
    if "scenes" not in sections:
        raise AdventureParseError("Missing ## Scenes section")
    scenes = _parse_scenes(sections["scenes"])
    if not scenes:
        raise AdventureParseError("No scenes found in ## Scenes section")

    return ParsedAdventure(
        name=title,
        description=description,
        narrator_context=narrator_context,
        setting=setting_ref,
        npcs=npcs,
        scenes=scenes,
    )


def parse_adventure_file(path: str | Path) -> ParsedAdventure:
    text = Path(path).read_text()
    return parse_adventure(text)


def validate_adventure(adventure: ParsedAdventure) -> list[str]:
    """Return a list of warnings (not errors) about the adventure."""
    warnings = []

    if len(adventure.scenes) < 2:
        warnings.append("Adventure has fewer than 2 scenes.")

    for scene in adventure.scenes:
        if not scene.encounters:
            warnings.append(f"Scene '{scene.name}' has no encounters.")

    for npc in adventure.npcs:
        if not npc.motivation:
            warnings.append(f"NPC '{npc.name}' has no motivation.")

    encounter_skills = set()
    for scene in adventure.scenes:
        for enc in scene.encounters:
            if enc.skill:
                encounter_skills.add(enc.skill)
    if encounter_skills:
        warnings.append(f"Skills referenced in encounters: {', '.join(sorted(encounter_skills))}")

    return warnings


def _join_lines(lines: list[str]) -> str:
    return "\n".join(lines).strip()


def _parse_npcs(lines: list[str]) -> list[ParsedNPC]:
    npcs = []
    current_name = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### "):
            if current_name:
                npcs.append(_build_npc(current_name, current_lines))
            current_name = stripped[4:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_name:
        npcs.append(_build_npc(current_name, current_lines))

    return npcs


def _build_npc(name: str, lines: list[str]) -> ParsedNPC:
    motivation = None
    desc_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("**motivation:**"):
            motivation = stripped.split(":", 1)[1].strip().rstrip("*")
        else:
            desc_lines.append(line)

    return ParsedNPC(
        name=name,
        description=_join_lines(desc_lines),
        motivation=motivation,
    )


def _parse_scenes(lines: list[str]) -> list[ParsedScene]:
    scenes = []
    current_name = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### ") and not stripped.startswith("#### "):
            if current_name:
                scenes.append(_build_scene(current_name, current_lines))
            current_name = stripped[4:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_name:
        scenes.append(_build_scene(current_name, current_lines))

    return scenes


def _build_scene(name: str, lines: list[str]) -> ParsedScene:
    # Split at #### Encounters
    desc_lines = []
    encounter_lines = []
    in_encounters = False

    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("#### encounters"):
            in_encounters = True
            continue
        if in_encounters:
            encounter_lines.append(line)
        else:
            desc_lines.append(line)

    encounters = []
    for line in encounter_lines:
        stripped = line.strip()
        if not stripped or not stripped.startswith("-"):
            continue
        # Try matching with skill/DC first
        m = _ENCOUNTER_RE.match(stripped)
        if m:
            encounters.append(ParsedEncounter(
                name=m.group(1).strip(),
                description=m.group(2).strip().rstrip("."),
                skill=m.group(3).strip(),
                dc=int(m.group(4)),
            ))
        else:
            # Fallback: encounter without skill/DC
            m2 = _ENCOUNTER_NO_SKILL_RE.match(stripped)
            if m2:
                encounters.append(ParsedEncounter(
                    name=m2.group(1).strip(),
                    description=m2.group(2).strip().rstrip("."),
                ))

    return ParsedScene(
        name=name,
        description=_join_lines(desc_lines),
        encounters=encounters,
    )
