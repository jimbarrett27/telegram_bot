"""
Pre-rolled character templates for each class at levels 1-5.

Defines starting attributes, HP, equipment, and spell slots based on
D&D 5e SRD rules.  HP uses max hit-die at level 1 and average rolls
for subsequent levels.  Ability scores stay fixed (no ASIs).
"""

from dnd.models import CharacterClass


# ---------------------------------------------------------------------------
# HP per level (max die at L1, average rounded up thereafter)
#   Warrior:   d10+2 CON  ->  12, 19, 26, 33, 40
#   Mage:      d6+1  CON  ->   7, 12, 17, 22, 27
#   Rogue:     d8+1  CON  ->   9, 15, 21, 27, 33
#   Cleric:    d8+1  CON  ->   9, 15, 21, 27, 33
#   Bard:      d8+1  CON  ->   9, 15, 21, 27, 33
#   Druid:     d8+2  CON  ->  10, 17, 24, 31, 38
#   Barbarian: d12+3 CON  ->  15, 23, 31, 39, 47
#   Monk:      d8+1  CON  ->   9, 15, 21, 27, 33
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Equipment helpers — shared across levels to avoid repetition
# ---------------------------------------------------------------------------

_WARRIOR_GEAR_L1 = [
    {"item_name": "Longsword", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Chain Mail", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Shield", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Handaxe", "item_type": "weapon", "quantity": 2, "equipped": False},
    {"item_name": "Explorer's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
]

_WARRIOR_GEAR_L3 = [
    {"item_name": "Longsword +1", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Splint Armor", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Shield", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Handaxe", "item_type": "weapon", "quantity": 2, "equipped": False},
    {"item_name": "Explorer's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Potion of Healing", "item_type": "gear", "quantity": 2, "equipped": False},
]

_WARRIOR_GEAR_L5 = [
    {"item_name": "Longsword +1", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Plate Armor", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Shield +1", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Handaxe", "item_type": "weapon", "quantity": 2, "equipped": False},
    {"item_name": "Explorer's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Potion of Healing", "item_type": "gear", "quantity": 3, "equipped": False},
]

_MAGE_GEAR_L1 = [
    {"item_name": "Quarterstaff", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Arcane Focus", "item_type": "gear", "quantity": 1, "equipped": True},
    {"item_name": "Scholar's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Spellbook", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Dagger", "item_type": "weapon", "quantity": 1, "equipped": False},
]

_MAGE_GEAR_L3 = [
    {"item_name": "Quarterstaff +1", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Arcane Focus", "item_type": "gear", "quantity": 1, "equipped": True},
    {"item_name": "Scholar's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Spellbook", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Dagger", "item_type": "weapon", "quantity": 1, "equipped": False},
    {"item_name": "Potion of Healing", "item_type": "gear", "quantity": 2, "equipped": False},
    {"item_name": "Scroll of Shield", "item_type": "gear", "quantity": 1, "equipped": False},
]

_MAGE_GEAR_L5 = [
    {"item_name": "Quarterstaff +1", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Arcane Focus +1", "item_type": "gear", "quantity": 1, "equipped": True},
    {"item_name": "Scholar's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Spellbook", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Dagger", "item_type": "weapon", "quantity": 1, "equipped": False},
    {"item_name": "Potion of Healing", "item_type": "gear", "quantity": 3, "equipped": False},
    {"item_name": "Scroll of Fireball", "item_type": "gear", "quantity": 1, "equipped": False},
]

_ROGUE_GEAR_L1 = [
    {"item_name": "Shortsword", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Shortbow", "item_type": "weapon", "quantity": 1, "equipped": False},
    {"item_name": "Arrows", "item_type": "gear", "quantity": 20, "equipped": False},
    {"item_name": "Leather Armor", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Dagger", "item_type": "weapon", "quantity": 2, "equipped": False},
    {"item_name": "Thieves' Tools", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Burglar's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
]

_ROGUE_GEAR_L3 = [
    {"item_name": "Shortsword +1", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Shortbow", "item_type": "weapon", "quantity": 1, "equipped": False},
    {"item_name": "Arrows", "item_type": "gear", "quantity": 20, "equipped": False},
    {"item_name": "Studded Leather Armor", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Dagger", "item_type": "weapon", "quantity": 2, "equipped": False},
    {"item_name": "Thieves' Tools", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Burglar's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Potion of Healing", "item_type": "gear", "quantity": 2, "equipped": False},
]

_ROGUE_GEAR_L5 = [
    {"item_name": "Shortsword +1", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Shortbow +1", "item_type": "weapon", "quantity": 1, "equipped": False},
    {"item_name": "Arrows", "item_type": "gear", "quantity": 20, "equipped": False},
    {"item_name": "Studded Leather Armor +1", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Dagger", "item_type": "weapon", "quantity": 2, "equipped": False},
    {"item_name": "Thieves' Tools", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Burglar's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Potion of Healing", "item_type": "gear", "quantity": 3, "equipped": False},
    {"item_name": "Cloak of Elvenkind", "item_type": "gear", "quantity": 1, "equipped": True},
]

_CLERIC_GEAR_L1 = [
    {"item_name": "Mace", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Scale Mail", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Shield", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Holy Symbol", "item_type": "gear", "quantity": 1, "equipped": True},
    {"item_name": "Priest's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Light Crossbow", "item_type": "weapon", "quantity": 1, "equipped": False},
    {"item_name": "Bolts", "item_type": "gear", "quantity": 20, "equipped": False},
]

_CLERIC_GEAR_L3 = [
    {"item_name": "Mace +1", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Chain Mail", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Shield", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Holy Symbol", "item_type": "gear", "quantity": 1, "equipped": True},
    {"item_name": "Priest's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Light Crossbow", "item_type": "weapon", "quantity": 1, "equipped": False},
    {"item_name": "Bolts", "item_type": "gear", "quantity": 20, "equipped": False},
    {"item_name": "Potion of Healing", "item_type": "gear", "quantity": 2, "equipped": False},
]

_CLERIC_GEAR_L5 = [
    {"item_name": "Mace +1", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Splint Armor", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Shield +1", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Holy Symbol", "item_type": "gear", "quantity": 1, "equipped": True},
    {"item_name": "Priest's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Light Crossbow", "item_type": "weapon", "quantity": 1, "equipped": False},
    {"item_name": "Bolts", "item_type": "gear", "quantity": 20, "equipped": False},
    {"item_name": "Potion of Healing", "item_type": "gear", "quantity": 3, "equipped": False},
    {"item_name": "Wand of Cure Wounds", "item_type": "gear", "quantity": 1, "equipped": False},
]

_BARD_GEAR_L1 = [
    {"item_name": "Rapier", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Leather Armor", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Lute", "item_type": "gear", "quantity": 1, "equipped": True},
    {"item_name": "Dagger", "item_type": "weapon", "quantity": 1, "equipped": False},
    {"item_name": "Entertainer's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
]

_BARD_GEAR_L3 = [
    {"item_name": "Rapier +1", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Studded Leather Armor", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Lute", "item_type": "gear", "quantity": 1, "equipped": True},
    {"item_name": "Dagger", "item_type": "weapon", "quantity": 1, "equipped": False},
    {"item_name": "Entertainer's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Potion of Healing", "item_type": "gear", "quantity": 2, "equipped": False},
]

_BARD_GEAR_L5 = [
    {"item_name": "Rapier +1", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Studded Leather Armor +1", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Lute of Illusions", "item_type": "gear", "quantity": 1, "equipped": True},
    {"item_name": "Dagger", "item_type": "weapon", "quantity": 1, "equipped": False},
    {"item_name": "Entertainer's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Potion of Healing", "item_type": "gear", "quantity": 3, "equipped": False},
]

_DRUID_GEAR_L1 = [
    {"item_name": "Scimitar", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Leather Armor", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Wooden Shield", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Druidic Focus", "item_type": "gear", "quantity": 1, "equipped": True},
    {"item_name": "Explorer's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Herbalism Kit", "item_type": "gear", "quantity": 1, "equipped": False},
]

_DRUID_GEAR_L3 = [
    {"item_name": "Scimitar +1", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Hide Armor", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Wooden Shield", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Druidic Focus", "item_type": "gear", "quantity": 1, "equipped": True},
    {"item_name": "Explorer's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Herbalism Kit", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Potion of Healing", "item_type": "gear", "quantity": 2, "equipped": False},
]

_DRUID_GEAR_L5 = [
    {"item_name": "Scimitar +1", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Hide Armor +1", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Wooden Shield +1", "item_type": "armor", "quantity": 1, "equipped": True},
    {"item_name": "Staff of the Woodlands", "item_type": "gear", "quantity": 1, "equipped": True},
    {"item_name": "Explorer's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Herbalism Kit", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Potion of Healing", "item_type": "gear", "quantity": 3, "equipped": False},
]

_BARBARIAN_GEAR_L1 = [
    {"item_name": "Greataxe", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Javelin", "item_type": "weapon", "quantity": 4, "equipped": False},
    {"item_name": "Explorer's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
]

_BARBARIAN_GEAR_L3 = [
    {"item_name": "Greataxe +1", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Javelin", "item_type": "weapon", "quantity": 4, "equipped": False},
    {"item_name": "Explorer's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Potion of Healing", "item_type": "gear", "quantity": 2, "equipped": False},
]

_BARBARIAN_GEAR_L5 = [
    {"item_name": "Greataxe +1", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Javelin", "item_type": "weapon", "quantity": 4, "equipped": False},
    {"item_name": "Explorer's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Potion of Healing", "item_type": "gear", "quantity": 3, "equipped": False},
    {"item_name": "Belt of Giant Strength", "item_type": "gear", "quantity": 1, "equipped": True},
]

_MONK_GEAR_L1 = [
    {"item_name": "Shortsword", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Dart", "item_type": "weapon", "quantity": 10, "equipped": False},
    {"item_name": "Explorer's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
]

_MONK_GEAR_L3 = [
    {"item_name": "Shortsword +1", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Dart", "item_type": "weapon", "quantity": 10, "equipped": False},
    {"item_name": "Explorer's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Potion of Healing", "item_type": "gear", "quantity": 2, "equipped": False},
]

_MONK_GEAR_L5 = [
    {"item_name": "Shortsword +1", "item_type": "weapon", "quantity": 1, "equipped": True},
    {"item_name": "Dart", "item_type": "weapon", "quantity": 10, "equipped": False},
    {"item_name": "Explorer's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
    {"item_name": "Potion of Healing", "item_type": "gear", "quantity": 3, "equipped": False},
    {"item_name": "Bracers of Defense", "item_type": "gear", "quantity": 1, "equipped": True},
]

# ---------------------------------------------------------------------------
# Base ability scores (constant across levels — no ASIs in this system)
# ---------------------------------------------------------------------------

_WARRIOR_ATTRS = {
    "strength": 16, "dexterity": 12, "constitution": 14,
    "intelligence": 8, "wisdom": 10, "charisma": 10,
}
_MAGE_ATTRS = {
    "strength": 8, "dexterity": 14, "constitution": 12,
    "intelligence": 16, "wisdom": 12, "charisma": 10,
}
_ROGUE_ATTRS = {
    "strength": 10, "dexterity": 16, "constitution": 12,
    "intelligence": 14, "wisdom": 10, "charisma": 8,
}
_CLERIC_ATTRS = {
    "strength": 14, "dexterity": 10, "constitution": 12,
    "intelligence": 8, "wisdom": 16, "charisma": 10,
}
_BARD_ATTRS = {
    "strength": 8, "dexterity": 14, "constitution": 12,
    "intelligence": 10, "wisdom": 10, "charisma": 16,
}
_DRUID_ATTRS = {
    "strength": 10, "dexterity": 12, "constitution": 14,
    "intelligence": 10, "wisdom": 16, "charisma": 8,
}
_BARBARIAN_ATTRS = {
    "strength": 16, "dexterity": 14, "constitution": 16,
    "intelligence": 8, "wisdom": 10, "charisma": 8,
}
_MONK_ATTRS = {
    "strength": 10, "dexterity": 16, "constitution": 12,
    "intelligence": 8, "wisdom": 16, "charisma": 8,
}

# ---------------------------------------------------------------------------
# Templates keyed by (CharacterClass, level)
# ---------------------------------------------------------------------------

CHARACTER_TEMPLATES: dict[tuple[CharacterClass, int], dict] = {
    # ── Warrior ───────────────────────────────────────────────────────────
    (CharacterClass.WARRIOR, 1): {
        "attributes": _WARRIOR_ATTRS,
        "hp": 12, "max_hp": 12,
        "starting_inventory": _WARRIOR_GEAR_L1,
        "spell_slots": {},
    },
    (CharacterClass.WARRIOR, 2): {
        "attributes": _WARRIOR_ATTRS,
        "hp": 19, "max_hp": 19,
        "starting_inventory": _WARRIOR_GEAR_L1,
        "spell_slots": {},
    },
    (CharacterClass.WARRIOR, 3): {
        "attributes": _WARRIOR_ATTRS,
        "hp": 26, "max_hp": 26,
        "starting_inventory": _WARRIOR_GEAR_L3,
        "spell_slots": {},
    },
    (CharacterClass.WARRIOR, 4): {
        "attributes": _WARRIOR_ATTRS,
        "hp": 33, "max_hp": 33,
        "starting_inventory": _WARRIOR_GEAR_L3,
        "spell_slots": {},
    },
    (CharacterClass.WARRIOR, 5): {
        "attributes": _WARRIOR_ATTRS,
        "hp": 40, "max_hp": 40,
        "starting_inventory": _WARRIOR_GEAR_L5,
        "spell_slots": {},
    },

    # ── Mage ──────────────────────────────────────────────────────────────
    (CharacterClass.MAGE, 1): {
        "attributes": _MAGE_ATTRS,
        "hp": 7, "max_hp": 7,
        "starting_inventory": _MAGE_GEAR_L1,
        "spell_slots": {"level_1": 2, "max_level_1": 2},
    },
    (CharacterClass.MAGE, 2): {
        "attributes": _MAGE_ATTRS,
        "hp": 12, "max_hp": 12,
        "starting_inventory": _MAGE_GEAR_L1,
        "spell_slots": {"level_1": 3, "max_level_1": 3},
    },
    (CharacterClass.MAGE, 3): {
        "attributes": _MAGE_ATTRS,
        "hp": 17, "max_hp": 17,
        "starting_inventory": _MAGE_GEAR_L3,
        "spell_slots": {"level_1": 4, "max_level_1": 4, "level_2": 2, "max_level_2": 2},
    },
    (CharacterClass.MAGE, 4): {
        "attributes": _MAGE_ATTRS,
        "hp": 22, "max_hp": 22,
        "starting_inventory": _MAGE_GEAR_L3,
        "spell_slots": {"level_1": 4, "max_level_1": 4, "level_2": 3, "max_level_2": 3},
    },
    (CharacterClass.MAGE, 5): {
        "attributes": _MAGE_ATTRS,
        "hp": 27, "max_hp": 27,
        "starting_inventory": _MAGE_GEAR_L5,
        "spell_slots": {
            "level_1": 4, "max_level_1": 4,
            "level_2": 3, "max_level_2": 3,
            "level_3": 2, "max_level_3": 2,
        },
    },

    # ── Rogue ─────────────────────────────────────────────────────────────
    (CharacterClass.ROGUE, 1): {
        "attributes": _ROGUE_ATTRS,
        "hp": 9, "max_hp": 9,
        "starting_inventory": _ROGUE_GEAR_L1,
        "spell_slots": {},
    },
    (CharacterClass.ROGUE, 2): {
        "attributes": _ROGUE_ATTRS,
        "hp": 15, "max_hp": 15,
        "starting_inventory": _ROGUE_GEAR_L1,
        "spell_slots": {},
    },
    (CharacterClass.ROGUE, 3): {
        "attributes": _ROGUE_ATTRS,
        "hp": 21, "max_hp": 21,
        "starting_inventory": _ROGUE_GEAR_L3,
        "spell_slots": {},
    },
    (CharacterClass.ROGUE, 4): {
        "attributes": _ROGUE_ATTRS,
        "hp": 27, "max_hp": 27,
        "starting_inventory": _ROGUE_GEAR_L3,
        "spell_slots": {},
    },
    (CharacterClass.ROGUE, 5): {
        "attributes": _ROGUE_ATTRS,
        "hp": 33, "max_hp": 33,
        "starting_inventory": _ROGUE_GEAR_L5,
        "spell_slots": {},
    },

    # ── Cleric ────────────────────────────────────────────────────────────
    (CharacterClass.CLERIC, 1): {
        "attributes": _CLERIC_ATTRS,
        "hp": 9, "max_hp": 9,
        "starting_inventory": _CLERIC_GEAR_L1,
        "spell_slots": {"level_1": 2, "max_level_1": 2},
    },
    (CharacterClass.CLERIC, 2): {
        "attributes": _CLERIC_ATTRS,
        "hp": 15, "max_hp": 15,
        "starting_inventory": _CLERIC_GEAR_L1,
        "spell_slots": {"level_1": 3, "max_level_1": 3},
    },
    (CharacterClass.CLERIC, 3): {
        "attributes": _CLERIC_ATTRS,
        "hp": 21, "max_hp": 21,
        "starting_inventory": _CLERIC_GEAR_L3,
        "spell_slots": {"level_1": 4, "max_level_1": 4, "level_2": 2, "max_level_2": 2},
    },
    (CharacterClass.CLERIC, 4): {
        "attributes": _CLERIC_ATTRS,
        "hp": 27, "max_hp": 27,
        "starting_inventory": _CLERIC_GEAR_L3,
        "spell_slots": {"level_1": 4, "max_level_1": 4, "level_2": 3, "max_level_2": 3},
    },
    (CharacterClass.CLERIC, 5): {
        "attributes": _CLERIC_ATTRS,
        "hp": 33, "max_hp": 33,
        "starting_inventory": _CLERIC_GEAR_L5,
        "spell_slots": {
            "level_1": 4, "max_level_1": 4,
            "level_2": 3, "max_level_2": 3,
            "level_3": 2, "max_level_3": 2,
        },
    },

    # ── Bard ──────────────────────────────────────────────────────────────
    # Full caster (d8+1 CON), CHA-based, same slot progression as cleric
    (CharacterClass.BARD, 1): {
        "attributes": _BARD_ATTRS,
        "hp": 9, "max_hp": 9,
        "starting_inventory": _BARD_GEAR_L1,
        "spell_slots": {"level_1": 2, "max_level_1": 2},
    },
    (CharacterClass.BARD, 2): {
        "attributes": _BARD_ATTRS,
        "hp": 15, "max_hp": 15,
        "starting_inventory": _BARD_GEAR_L1,
        "spell_slots": {"level_1": 3, "max_level_1": 3},
    },
    (CharacterClass.BARD, 3): {
        "attributes": _BARD_ATTRS,
        "hp": 21, "max_hp": 21,
        "starting_inventory": _BARD_GEAR_L3,
        "spell_slots": {"level_1": 4, "max_level_1": 4, "level_2": 2, "max_level_2": 2},
    },
    (CharacterClass.BARD, 4): {
        "attributes": _BARD_ATTRS,
        "hp": 27, "max_hp": 27,
        "starting_inventory": _BARD_GEAR_L3,
        "spell_slots": {"level_1": 4, "max_level_1": 4, "level_2": 3, "max_level_2": 3},
    },
    (CharacterClass.BARD, 5): {
        "attributes": _BARD_ATTRS,
        "hp": 33, "max_hp": 33,
        "starting_inventory": _BARD_GEAR_L5,
        "spell_slots": {
            "level_1": 4, "max_level_1": 4,
            "level_2": 3, "max_level_2": 3,
            "level_3": 2, "max_level_3": 2,
        },
    },

    # ── Druid ─────────────────────────────────────────────────────────────
    # Full caster (d8+2 CON), WIS-based, same slot progression as cleric
    (CharacterClass.DRUID, 1): {
        "attributes": _DRUID_ATTRS,
        "hp": 10, "max_hp": 10,
        "starting_inventory": _DRUID_GEAR_L1,
        "spell_slots": {"level_1": 2, "max_level_1": 2},
    },
    (CharacterClass.DRUID, 2): {
        "attributes": _DRUID_ATTRS,
        "hp": 17, "max_hp": 17,
        "starting_inventory": _DRUID_GEAR_L1,
        "spell_slots": {"level_1": 3, "max_level_1": 3},
    },
    (CharacterClass.DRUID, 3): {
        "attributes": _DRUID_ATTRS,
        "hp": 24, "max_hp": 24,
        "starting_inventory": _DRUID_GEAR_L3,
        "spell_slots": {"level_1": 4, "max_level_1": 4, "level_2": 2, "max_level_2": 2},
    },
    (CharacterClass.DRUID, 4): {
        "attributes": _DRUID_ATTRS,
        "hp": 31, "max_hp": 31,
        "starting_inventory": _DRUID_GEAR_L3,
        "spell_slots": {"level_1": 4, "max_level_1": 4, "level_2": 3, "max_level_2": 3},
    },
    (CharacterClass.DRUID, 5): {
        "attributes": _DRUID_ATTRS,
        "hp": 38, "max_hp": 38,
        "starting_inventory": _DRUID_GEAR_L5,
        "spell_slots": {
            "level_1": 4, "max_level_1": 4,
            "level_2": 3, "max_level_2": 3,
            "level_3": 2, "max_level_3": 2,
        },
    },

    # ── Barbarian ─────────────────────────────────────────────────────────
    # Martial (d12+3 CON), STR-based, no spells, unarmored
    (CharacterClass.BARBARIAN, 1): {
        "attributes": _BARBARIAN_ATTRS,
        "hp": 15, "max_hp": 15,
        "starting_inventory": _BARBARIAN_GEAR_L1,
        "spell_slots": {},
    },
    (CharacterClass.BARBARIAN, 2): {
        "attributes": _BARBARIAN_ATTRS,
        "hp": 23, "max_hp": 23,
        "starting_inventory": _BARBARIAN_GEAR_L1,
        "spell_slots": {},
    },
    (CharacterClass.BARBARIAN, 3): {
        "attributes": _BARBARIAN_ATTRS,
        "hp": 31, "max_hp": 31,
        "starting_inventory": _BARBARIAN_GEAR_L3,
        "spell_slots": {},
    },
    (CharacterClass.BARBARIAN, 4): {
        "attributes": _BARBARIAN_ATTRS,
        "hp": 39, "max_hp": 39,
        "starting_inventory": _BARBARIAN_GEAR_L3,
        "spell_slots": {},
    },
    (CharacterClass.BARBARIAN, 5): {
        "attributes": _BARBARIAN_ATTRS,
        "hp": 47, "max_hp": 47,
        "starting_inventory": _BARBARIAN_GEAR_L5,
        "spell_slots": {},
    },

    # ── Monk ──────────────────────────────────────────────────────────────
    # Martial (d8+1 CON), DEX/WIS-based, no spells, unarmored defense
    (CharacterClass.MONK, 1): {
        "attributes": _MONK_ATTRS,
        "hp": 9, "max_hp": 9,
        "starting_inventory": _MONK_GEAR_L1,
        "spell_slots": {},
    },
    (CharacterClass.MONK, 2): {
        "attributes": _MONK_ATTRS,
        "hp": 15, "max_hp": 15,
        "starting_inventory": _MONK_GEAR_L1,
        "spell_slots": {},
    },
    (CharacterClass.MONK, 3): {
        "attributes": _MONK_ATTRS,
        "hp": 21, "max_hp": 21,
        "starting_inventory": _MONK_GEAR_L3,
        "spell_slots": {},
    },
    (CharacterClass.MONK, 4): {
        "attributes": _MONK_ATTRS,
        "hp": 27, "max_hp": 27,
        "starting_inventory": _MONK_GEAR_L3,
        "spell_slots": {},
    },
    (CharacterClass.MONK, 5): {
        "attributes": _MONK_ATTRS,
        "hp": 33, "max_hp": 33,
        "starting_inventory": _MONK_GEAR_L5,
        "spell_slots": {},
    },
}


def get_template(character_class: CharacterClass, level: int = 1) -> dict:
    """Get the character template for a class at a given level (1-5).

    Returns a dict with 'attributes', 'hp', 'max_hp', 'starting_inventory', 'spell_slots'.
    """
    level = max(1, min(level, 5))
    return CHARACTER_TEMPLATES[(character_class, level)]
