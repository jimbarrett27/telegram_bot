"""
SRD data access layer.

Loads bundled D&D 5e SRD JSON files and provides search/lookup methods
for equipment, spells, rules, and class spell lists.

Data sourced from https://github.com/BTMorton/dnd-5e-srd (CC-BY-4.0).
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SRD_DIR = Path(__file__).parent / "srd"


class SRDLookup:
    """Loads and searches bundled SRD JSON data.

    Lazy-loads each JSON file on first access and caches in memory.
    All public methods return formatted strings suitable for LLM tool responses.
    """

    def __init__(self):
        self._equipment_data: dict | None = None
        self._spellcasting_data: dict | None = None
        self._mechanics_data: dict | None = None
        self._combat_data: dict | None = None
        self._weapons_index: dict | None = None
        self._armor_index: dict | None = None
        self._spell_index: dict | None = None

    def _load_json(self, filename: str) -> dict:
        path = SRD_DIR / filename
        with open(path, "r") as f:
            return json.load(f)

    @property
    def equipment(self) -> dict:
        if self._equipment_data is None:
            self._equipment_data = self._load_json("equipment.json")["Equipment"]
        return self._equipment_data

    @property
    def spellcasting(self) -> dict:
        if self._spellcasting_data is None:
            self._spellcasting_data = self._load_json("spellcasting.json")["Spellcasting"]
        return self._spellcasting_data

    @property
    def mechanics(self) -> dict:
        if self._mechanics_data is None:
            raw = self._load_json("mechanics.json")
            self._mechanics_data = raw
        return self._mechanics_data

    @property
    def combat(self) -> dict:
        if self._combat_data is None:
            self._combat_data = self._load_json("combat.json")["Combat"]
        return self._combat_data

    def _build_weapons_index(self) -> dict[str, dict]:
        """Build a name→stats index from the weapons tables."""
        if self._weapons_index is not None:
            return self._weapons_index

        index = {}
        weapons = self.equipment.get("Weapons", {})
        weapons_list = weapons.get("Weapons List", {})

        for category, data in weapons_list.items():
            table = data.get("table", {})
            names = table.get("Name", [])
            costs = table.get("Cost", [])
            damages = table.get("Damage", [])
            weights = table.get("Weight", [])
            properties = table.get("Properties", [])

            for i, name in enumerate(names):
                index[name.lower()] = {
                    "name": name,
                    "category": category,
                    "cost": costs[i] if i < len(costs) else "—",
                    "damage": damages[i] if i < len(damages) else "—",
                    "weight": weights[i] if i < len(weights) else "—",
                    "properties": properties[i] if i < len(properties) else "—",
                }

        self._weapons_index = index
        return index

    def _build_armor_index(self) -> dict[str, dict]:
        """Build a name→stats index from the armor tables."""
        if self._armor_index is not None:
            return self._armor_index

        index = {}
        armor = self.equipment.get("Armor", {})
        armor_list = armor.get("Armor List", {})

        for category, data in armor_list.items():
            table = data.get("table", {})
            names = table.get("Armor", [])
            costs = table.get("Cost", [])
            acs = table.get("Armor Class (AC)", [])
            strengths = table.get("Strength", [])
            stealths = table.get("Stealth", [])
            weights = table.get("Weight", [])

            for i, name in enumerate(names):
                index[name.lower()] = {
                    "name": name,
                    "category": category,
                    "cost": costs[i] if i < len(costs) else "—",
                    "ac": acs[i] if i < len(acs) else "—",
                    "strength": strengths[i] if i < len(strengths) else "—",
                    "stealth": stealths[i] if i < len(stealths) else "—",
                    "weight": weights[i] if i < len(weights) else "—",
                }

        self._armor_index = index
        return index

    def _build_spell_index(self) -> dict[str, dict]:
        """Build a name→details index from spell descriptions."""
        if self._spell_index is not None:
            return self._spell_index

        index = {}
        descs = self.spellcasting.get("Spell Descriptions", {})
        for name, data in descs.items():
            content = data.get("content", []) if isinstance(data, dict) else []
            index[name.lower()] = {
                "name": name,
                "content": content,
            }

        self._spell_index = index
        return index

    def get_equipment(self, name: str) -> str:
        """Look up a specific piece of equipment by name.

        Searches weapons and armor indexes. Returns formatted stats or 'not found'.
        """
        name_lower = name.strip().lower()

        weapons = self._build_weapons_index()
        if name_lower in weapons:
            w = weapons[name_lower]
            return (
                f"Weapon: {w['name']}\n"
                f"  Category: {w['category']}\n"
                f"  Damage: {w['damage']}\n"
                f"  Cost: {w['cost']}\n"
                f"  Weight: {w['weight']}\n"
                f"  Properties: {w['properties']}"
            )

        armor = self._build_armor_index()
        if name_lower in armor:
            a = armor[name_lower]
            return (
                f"Armor: {a['name']}\n"
                f"  Category: {a['category']}\n"
                f"  AC: {a['ac']}\n"
                f"  Cost: {a['cost']}\n"
                f"  Strength: {a['strength']}\n"
                f"  Stealth: {a['stealth']}\n"
                f"  Weight: {a['weight']}"
            )

        return f"Equipment '{name}' not found in SRD."

    def search_equipment(self, query: str) -> str:
        """Search equipment by partial name match. Returns up to 10 matches."""
        query_lower = query.strip().lower()
        matches = []

        for name, stats in self._build_weapons_index().items():
            if query_lower in name:
                matches.append(f"  [Weapon] {stats['name']} — {stats['damage']}, {stats['properties']}")

        for name, stats in self._build_armor_index().items():
            if query_lower in name:
                matches.append(f"  [Armor] {stats['name']} — AC: {stats['ac']}")

        if not matches:
            return f"No equipment matching '{query}' found."

        return f"Equipment matching '{query}':\n" + "\n".join(matches[:10])

    def get_spell(self, name: str) -> str:
        """Look up a specific spell by name. Returns full spell description."""
        spells = self._build_spell_index()
        name_lower = name.strip().lower()

        if name_lower in spells:
            spell = spells[name_lower]
            return f"Spell: {spell['name']}\n" + "\n".join(spell["content"])

        return f"Spell '{name}' not found in SRD."

    def search_spells(self, query: str) -> str:
        """Search spells by partial name match. Returns up to 10 matches."""
        query_lower = query.strip().lower()
        spells = self._build_spell_index()
        matches = [s["name"] for name, s in spells.items() if query_lower in name]

        if not matches:
            return f"No spells matching '{query}' found."

        return f"Spells matching '{query}':\n" + "\n".join(f"  - {m}" for m in matches[:10])

    def get_class_spell_list(self, class_name: str) -> str:
        """Get the spell list for a character class.

        Args:
            class_name: Class name (e.g. 'cleric', 'wizard', 'mage')
        """
        # Map our class names to SRD spell list names
        class_map = {
            "cleric": "Cleric Spells",
            "mage": "Wizard Spells",
            "wizard": "Wizard Spells",
            "warrior": None,
            "fighter": None,
            "rogue": None,
        }

        class_lower = class_name.strip().lower()
        spell_list_key = class_map.get(class_lower)

        if spell_list_key is None:
            return f"The {class_name} class does not have a spell list."

        spell_lists = self.spellcasting.get("Spell Lists", {})
        class_spells = spell_lists.get(spell_list_key, {})

        if not class_spells:
            return f"No spell list found for '{class_name}'."

        lines = [f"Spell list for {class_name.title()}:"]
        for level, spells in class_spells.items():
            if isinstance(spells, list):
                lines.append(f"\n  {level}:")
                for s in spells:
                    lines.append(f"    - {s}")

        return "\n".join(lines)

    def lookup_rule(self, topic: str) -> str:
        """Search combat and mechanics rules by topic keyword.

        Args:
            topic: A rule topic to search for (e.g. 'grapple', 'cover', 'opportunity attack')
        """
        topic_lower = topic.strip().lower()
        results = []

        # Search combat rules
        for section_name, section_data in self.combat.items():
            if self._section_matches(section_name, section_data, topic_lower):
                text = self._format_section(section_name, section_data)
                results.append(text)

        # Search mechanics rules
        for top_key, top_data in self.mechanics.items():
            if isinstance(top_data, dict):
                for section_name, section_data in top_data.items():
                    if self._section_matches(section_name, section_data, topic_lower):
                        text = self._format_section(section_name, section_data)
                        results.append(text)

        if not results:
            return f"No rules found for topic '{topic}'."

        # Limit output size
        combined = "\n\n---\n\n".join(results[:3])
        if len(combined) > 3000:
            combined = combined[:3000] + "\n... (truncated)"
        return combined

    def _section_matches(self, name: str, data, topic: str) -> bool:
        """Check if a section name or content matches the topic."""
        if topic in name.lower():
            return True
        if isinstance(data, dict):
            content = data.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, str) and topic in item.lower():
                        return True
        return False

    def _format_section(self, name: str, data) -> str:
        """Format a rules section for display."""
        if isinstance(data, dict):
            content = data.get("content", [])
            if isinstance(content, list):
                text_parts = [item for item in content if isinstance(item, str)]
                return f"## {name}\n" + "\n".join(text_parts[:10])
            return f"## {name}\n(complex section)"
        elif isinstance(data, str):
            return f"## {name}\n{data}"
        return f"## {name}\n{str(data)[:500]}"


# Module-level singleton for reuse
_srd: SRDLookup | None = None


def get_srd() -> SRDLookup:
    """Get or create the module-level SRDLookup singleton."""
    global _srd
    if _srd is None:
        _srd = SRDLookup()
    return _srd
