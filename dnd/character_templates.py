"""
Pre-rolled character templates for each class.

Defines starting attributes, HP, equipment, and spell slots based on
D&D 5e SRD rules for level 1 characters.
"""

from dnd.models import CharacterClass


CHARACTER_TEMPLATES = {
    CharacterClass.WARRIOR: {
        "attributes": {
            "strength": 16,
            "dexterity": 12,
            "constitution": 14,
            "intelligence": 8,
            "wisdom": 10,
            "charisma": 10,
        },
        "hp": 12,  # d10 + CON mod (+2)
        "max_hp": 12,
        "starting_inventory": [
            {"item_name": "Longsword", "item_type": "weapon", "quantity": 1, "equipped": True},
            {"item_name": "Chain Mail", "item_type": "armor", "quantity": 1, "equipped": True},
            {"item_name": "Shield", "item_type": "armor", "quantity": 1, "equipped": True},
            {"item_name": "Handaxe", "item_type": "weapon", "quantity": 2, "equipped": False},
            {"item_name": "Explorer's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
        ],
        "spell_slots": {},
    },
    CharacterClass.MAGE: {
        "attributes": {
            "strength": 8,
            "dexterity": 14,
            "constitution": 12,
            "intelligence": 16,
            "wisdom": 12,
            "charisma": 10,
        },
        "hp": 7,  # d6 + CON mod (+1)
        "max_hp": 7,
        "starting_inventory": [
            {"item_name": "Quarterstaff", "item_type": "weapon", "quantity": 1, "equipped": True},
            {"item_name": "Arcane Focus", "item_type": "gear", "quantity": 1, "equipped": True},
            {"item_name": "Scholar's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
            {"item_name": "Spellbook", "item_type": "gear", "quantity": 1, "equipped": False},
            {"item_name": "Dagger", "item_type": "weapon", "quantity": 1, "equipped": False},
        ],
        "spell_slots": {"level_1": 2, "max_level_1": 2},
    },
    CharacterClass.ROGUE: {
        "attributes": {
            "strength": 10,
            "dexterity": 16,
            "constitution": 12,
            "intelligence": 14,
            "wisdom": 10,
            "charisma": 8,
        },
        "hp": 9,  # d8 + CON mod (+1)
        "max_hp": 9,
        "starting_inventory": [
            {"item_name": "Shortsword", "item_type": "weapon", "quantity": 1, "equipped": True},
            {"item_name": "Shortbow", "item_type": "weapon", "quantity": 1, "equipped": False},
            {"item_name": "Arrows", "item_type": "gear", "quantity": 20, "equipped": False},
            {"item_name": "Leather Armor", "item_type": "armor", "quantity": 1, "equipped": True},
            {"item_name": "Dagger", "item_type": "weapon", "quantity": 2, "equipped": False},
            {"item_name": "Thieves' Tools", "item_type": "gear", "quantity": 1, "equipped": False},
            {"item_name": "Burglar's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
        ],
        "spell_slots": {},
    },
    CharacterClass.CLERIC: {
        "attributes": {
            "strength": 14,
            "dexterity": 10,
            "constitution": 12,
            "intelligence": 8,
            "wisdom": 16,
            "charisma": 10,
        },
        "hp": 9,  # d8 + CON mod (+1)
        "max_hp": 9,
        "starting_inventory": [
            {"item_name": "Mace", "item_type": "weapon", "quantity": 1, "equipped": True},
            {"item_name": "Scale Mail", "item_type": "armor", "quantity": 1, "equipped": True},
            {"item_name": "Shield", "item_type": "armor", "quantity": 1, "equipped": True},
            {"item_name": "Holy Symbol", "item_type": "gear", "quantity": 1, "equipped": True},
            {"item_name": "Priest's Pack", "item_type": "gear", "quantity": 1, "equipped": False},
            {"item_name": "Light Crossbow", "item_type": "weapon", "quantity": 1, "equipped": False},
            {"item_name": "Bolts", "item_type": "gear", "quantity": 20, "equipped": False},
        ],
        "spell_slots": {"level_1": 2, "max_level_1": 2},
    },
}


def get_template(character_class: CharacterClass) -> dict:
    """Get the character template for a class.

    Returns a dict with 'attributes', 'hp', 'max_hp', 'starting_inventory', 'spell_slots'.
    """
    return CHARACTER_TEMPLATES[character_class]
