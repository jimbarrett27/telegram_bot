"""Tests for SRD data lookup."""

import pytest

from dnd.srd_lookup import SRDLookup


@pytest.fixture
def srd():
    return SRDLookup()


class TestGetEquipment:

    def test_longsword(self, srd):
        result = srd.get_equipment("Longsword")
        assert "Longsword" in result
        assert "1d8" in result
        assert "Weapon" in result

    def test_case_insensitive(self, srd):
        result = srd.get_equipment("longsword")
        assert "Longsword" in result

    def test_not_found(self, srd):
        result = srd.get_equipment("Plasma Rifle")
        assert "not found" in result

    def test_armor(self, srd):
        result = srd.get_equipment("Chain Mail")
        assert "Chain" in result
        assert "AC" in result


class TestSearchEquipment:

    def test_search_sword(self, srd):
        result = srd.search_equipment("sword")
        assert "sword" in result.lower()

    def test_search_no_results(self, srd):
        result = srd.search_equipment("zzznonexistent")
        assert "No equipment" in result


class TestGetSpell:

    def test_fireball(self, srd):
        result = srd.get_spell("Fireball")
        assert "Fireball" in result
        assert "evocation" in result.lower()

    def test_cure_wounds(self, srd):
        result = srd.get_spell("Cure Wounds")
        assert "Cure Wounds" in result

    def test_case_insensitive(self, srd):
        result = srd.get_spell("fireball")
        assert "Fireball" in result

    def test_not_found(self, srd):
        result = srd.get_spell("Mega Death Ray")
        assert "not found" in result


class TestSearchSpells:

    def test_search_fire(self, srd):
        result = srd.search_spells("fire")
        assert "fire" in result.lower()

    def test_search_no_results(self, srd):
        result = srd.search_spells("zzznonexistent")
        assert "No spells" in result


class TestGetClassSpellList:

    def test_cleric(self, srd):
        result = srd.get_class_spell_list("cleric")
        assert "Cleric" in result
        assert "Cure Wounds" in result

    def test_mage_maps_to_wizard(self, srd):
        result = srd.get_class_spell_list("mage")
        assert "Mage" in result or "Wizard" in result

    def test_warrior_no_spells(self, srd):
        result = srd.get_class_spell_list("warrior")
        assert "does not have" in result

    def test_rogue_no_spells(self, srd):
        result = srd.get_class_spell_list("rogue")
        assert "does not have" in result


class TestLookupRule:

    def test_cover(self, srd):
        result = srd.lookup_rule("cover")
        assert "cover" in result.lower() or "Cover" in result

    def test_no_results(self, srd):
        result = srd.lookup_rule("zzznonexistentrule")
        assert "No rules found" in result
