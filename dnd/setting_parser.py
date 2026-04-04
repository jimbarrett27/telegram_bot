"""Parse setting markdown files into structured data for character creation.

Expected format:

    # Setting Name

    Description.

    ## Skills

    - Skill Name — Description

    ## Classes

    ### Character Class Name
    Description of the class.

    #### Skills
    - Skill Name (level)

    #### Starting Items
    - Item Name (xQuantity) — Description
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedSkillDef:
    """A skill defined at the setting level."""
    name: str
    description: str


@dataclass
class ParsedClassSkill:
    """A skill reference on a character class — just name and level."""
    name: str
    level: int


@dataclass
class ParsedItemEntry:
    name: str
    quantity: int
    description: str


@dataclass
class ParsedCharacterClass:
    name: str
    description: str
    skills: list[ParsedClassSkill] = field(default_factory=list)
    starting_items: list[ParsedItemEntry] = field(default_factory=list)


@dataclass
class ParsedSetting:
    name: str
    description: str
    skills: list[ParsedSkillDef] = field(default_factory=list)
    classes: list[ParsedCharacterClass] = field(default_factory=list)


class SettingParseError(Exception):
    pass


_SKILL_DEF_RE = re.compile(
    r"^\-\s+(.+?)\s*[—–-]\s*(.+)$"
)

_CLASS_SKILL_RE = re.compile(
    r"^\-\s+(.+?)\s+\((\d+)\)\s*$"
)

_ITEM_RE = re.compile(
    r"^\-\s+(.+?)\s+\(x(\d+)\)\s*[—–-]\s*(.+)$"
)


def parse_setting(text: str) -> ParsedSetting:
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
        raise SettingParseError("Missing setting title (# Title)")

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

    description = _join_lines(sections.get("_preamble", []))
    if not description:
        raise SettingParseError("Missing setting description (text after title, before first ## section)")

    # Skills
    if "skills" not in sections:
        raise SettingParseError("Missing ## Skills section")
    skills = _parse_skill_defs(sections["skills"])
    if not skills:
        raise SettingParseError("No skills found in ## Skills section")

    # Classes
    if "classes" not in sections:
        raise SettingParseError("Missing ## Classes section")
    classes = _parse_classes(sections["classes"])
    if not classes:
        raise SettingParseError("No classes found in ## Classes section")

    return ParsedSetting(
        name=title,
        description=description,
        skills=skills,
        classes=classes,
    )


def parse_setting_file(path: str | Path) -> ParsedSetting:
    text = Path(path).read_text()
    return parse_setting(text)


def validate_setting(setting: ParsedSetting) -> list[str]:
    """Return a list of warnings about the setting."""
    warnings = []

    if len(setting.classes) < 2:
        warnings.append("Setting has fewer than 2 character classes.")

    defined_skills = {s.name for s in setting.skills}

    for cls in setting.classes:
        if not cls.skills:
            warnings.append(f"Class '{cls.name}' has no skills.")
        if not cls.starting_items:
            warnings.append(f"Class '{cls.name}' has no starting items.")
        for skill in cls.skills:
            if skill.name not in defined_skills:
                warnings.append(f"Class '{cls.name}' references undefined skill '{skill.name}'.")

    # Check all defined skills are used by at least one class
    used_skills = set()
    for cls in setting.classes:
        for skill in cls.skills:
            used_skills.add(skill.name)
    unused = defined_skills - used_skills
    for name in sorted(unused):
        warnings.append(f"Skill '{name}' is defined but not used by any class.")

    return warnings


def validate_adventure_skills(adventure_skills: set[str], setting: ParsedSetting) -> list[str]:
    """Check that all skills referenced in an adventure exist in the setting."""
    defined_skills = {s.name for s in setting.skills}
    warnings = []
    for skill in sorted(adventure_skills - defined_skills):
        warnings.append(f"Adventure references skill '{skill}' not defined in setting '{setting.name}'.")
    return warnings


def _join_lines(lines: list[str]) -> str:
    return "\n".join(lines).strip()


def _parse_skill_defs(lines: list[str]) -> list[ParsedSkillDef]:
    skills = []
    for line in lines:
        stripped = line.strip()
        if not stripped or not stripped.startswith("-"):
            continue
        m = _SKILL_DEF_RE.match(stripped)
        if m:
            skills.append(ParsedSkillDef(
                name=m.group(1).strip(),
                description=m.group(2).strip(),
            ))
    return skills


def _parse_classes(lines: list[str]) -> list[ParsedCharacterClass]:
    classes = []
    current_name = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### ") and not stripped.startswith("#### "):
            if current_name:
                classes.append(_build_character_class(current_name, current_lines))
            current_name = stripped[4:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_name:
        classes.append(_build_character_class(current_name, current_lines))

    return classes


def _build_character_class(name: str, lines: list[str]) -> ParsedCharacterClass:
    desc_lines = []
    current_subsection = None
    subsections: dict[str, list[str]] = {}

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#### "):
            current_subsection = stripped[5:].strip().lower()
            subsections[current_subsection] = []
        elif current_subsection is not None:
            subsections[current_subsection].append(line)
        else:
            desc_lines.append(line)

    skills = []
    for line in subsections.get("skills", []):
        stripped = line.strip()
        if not stripped or not stripped.startswith("-"):
            continue
        m = _CLASS_SKILL_RE.match(stripped)
        if m:
            skills.append(ParsedClassSkill(
                name=m.group(1).strip(),
                level=int(m.group(2)),
            ))

    items = []
    for line in subsections.get("starting items", []):
        stripped = line.strip()
        if not stripped or not stripped.startswith("-"):
            continue
        m = _ITEM_RE.match(stripped)
        if m:
            items.append(ParsedItemEntry(
                name=m.group(1).strip(),
                quantity=int(m.group(2)),
                description=m.group(3).strip(),
            ))

    return ParsedCharacterClass(
        name=name,
        description=_join_lines(desc_lines),
        skills=skills,
        starting_items=items,
    )
