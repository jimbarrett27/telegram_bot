"""Tests for character templates."""

import pytest

from dnd.models import CharacterClass
from dnd.character_templates import get_template, CHARACTER_TEMPLATES


class TestCharacterTemplates:

    def test_all_classes_have_templates(self):
        for cls in CharacterClass:
            assert cls in CHARACTER_TEMPLATES, f"Missing template for {cls}"

    @pytest.mark.parametrize("cls", list(CharacterClass))
    def test_template_has_required_keys(self, cls):
        template = get_template(cls)
        assert "attributes" in template
        assert "hp" in template
        assert "max_hp" in template
        assert "starting_inventory" in template
        assert "spell_slots" in template

    @pytest.mark.parametrize("cls", list(CharacterClass))
    def test_attributes_complete(self, cls):
        attrs = get_template(cls)["attributes"]
        for attr in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            assert attr in attrs
            assert isinstance(attrs[attr], int)
            assert 3 <= attrs[attr] <= 20

    @pytest.mark.parametrize("cls", list(CharacterClass))
    def test_hp_positive(self, cls):
        template = get_template(cls)
        assert template["hp"] > 0
        assert template["max_hp"] > 0
        assert template["hp"] == template["max_hp"]

    @pytest.mark.parametrize("cls", list(CharacterClass))
    def test_inventory_items_have_required_fields(self, cls):
        template = get_template(cls)
        for item in template["starting_inventory"]:
            assert "item_name" in item
            assert "item_type" in item
            assert "quantity" in item
            assert item["quantity"] >= 1

    def test_warrior_has_weapon(self):
        template = get_template(CharacterClass.WARRIOR)
        weapon_names = [i["item_name"] for i in template["starting_inventory"] if i["item_type"] == "weapon"]
        assert len(weapon_names) > 0

    def test_mage_has_spell_slots(self):
        template = get_template(CharacterClass.MAGE)
        assert template["spell_slots"].get("level_1", 0) > 0

    def test_cleric_has_spell_slots(self):
        template = get_template(CharacterClass.CLERIC)
        assert template["spell_slots"].get("level_1", 0) > 0

    def test_warrior_no_spell_slots(self):
        template = get_template(CharacterClass.WARRIOR)
        assert template["spell_slots"] == {}

    def test_rogue_no_spell_slots(self):
        template = get_template(CharacterClass.ROGUE)
        assert template["spell_slots"] == {}
