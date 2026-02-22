"""Tests for inventory and spell slot database operations."""

import pytest
from sqlalchemy import create_engine

from dnd import db_engine
from dnd.orm_models import Base
from dnd.models import CharacterClass, EventType
from dnd.database import (
    create_game,
    add_player,
    add_inventory_item,
    get_player_inventory,
    update_inventory_item_quantity,
    update_inventory_item_equipped,
    remove_inventory_item_by_name,
    create_spell_slots,
    get_spell_slots,
    use_spell_slot,
    restore_spell_slots,
    get_player_attributes,
    update_player_attributes,
)


@pytest.fixture
def temp_db():
    """Create a temporary in-memory database for testing."""
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)
    db_engine.set_engine(test_engine)
    yield test_engine
    db_engine.reset_engine()


@pytest.fixture
def player(temp_db):
    """Create a game with one player."""
    game = create_game(chat_id=12345)
    p = add_player(
        game_id=game.id,
        telegram_user_id=100,
        telegram_username="alice",
        character_name="Aragorn",
        character_class=CharacterClass.WARRIOR,
        hp=12,
        max_hp=12,
        strength=16,
        dexterity=12,
        constitution=14,
    )
    return p, game


class TestInventoryOperations:

    def test_add_and_get_inventory(self, player):
        p, game = player
        add_inventory_item(p.id, game.id, "Longsword", "weapon", 1, True)
        add_inventory_item(p.id, game.id, "Health Potion", "potion", 3)

        items = get_player_inventory(p.id)
        assert len(items) == 2
        assert items[0].item_name == "Longsword"
        assert items[0].equipped is True
        assert items[1].item_name == "Health Potion"
        assert items[1].quantity == 3

    def test_empty_inventory(self, player):
        p, game = player
        items = get_player_inventory(p.id)
        assert items == []

    def test_update_quantity(self, player):
        p, game = player
        item = add_inventory_item(p.id, game.id, "Arrows", "gear", 20)
        update_inventory_item_quantity(item.id, 15)

        items = get_player_inventory(p.id)
        assert items[0].quantity == 15

    def test_update_quantity_deletes_at_zero(self, player):
        p, game = player
        item = add_inventory_item(p.id, game.id, "Potion", "potion", 1)
        update_inventory_item_quantity(item.id, 0)

        items = get_player_inventory(p.id)
        assert len(items) == 0

    def test_equip_unequip(self, player):
        p, game = player
        item = add_inventory_item(p.id, game.id, "Shield", "armor", 1, False)

        update_inventory_item_equipped(item.id, True)
        items = get_player_inventory(p.id)
        assert items[0].equipped is True

        update_inventory_item_equipped(item.id, False)
        items = get_player_inventory(p.id)
        assert items[0].equipped is False

    def test_remove_by_name(self, player):
        p, game = player
        add_inventory_item(p.id, game.id, "Handaxe", "weapon", 2)

        result = remove_inventory_item_by_name(p.id, "Handaxe", 1)
        assert result is True

        items = get_player_inventory(p.id)
        assert items[0].quantity == 1

    def test_remove_by_name_deletes(self, player):
        p, game = player
        add_inventory_item(p.id, game.id, "Torch", "gear", 1)

        result = remove_inventory_item_by_name(p.id, "Torch", 1)
        assert result is True

        items = get_player_inventory(p.id)
        assert len(items) == 0

    def test_remove_by_name_not_found(self, player):
        p, game = player
        result = remove_inventory_item_by_name(p.id, "Nonexistent", 1)
        assert result is False


class TestSpellSlotOperations:

    def test_create_and_get(self, player):
        p, game = player
        create_spell_slots(player_id=p.id, level_1=2, max_level_1=2)

        slots = get_spell_slots(p.id)
        assert slots is not None
        assert slots.level_1 == 2
        assert slots.max_level_1 == 2
        assert slots.level_2 == 0

    def test_use_spell_slot(self, player):
        p, game = player
        create_spell_slots(player_id=p.id, level_1=2, max_level_1=2)

        result = use_spell_slot(p.id, 1)
        assert result is True

        slots = get_spell_slots(p.id)
        assert slots.level_1 == 1

    def test_use_spell_slot_empty(self, player):
        p, game = player
        create_spell_slots(player_id=p.id, level_1=0, max_level_1=2)

        result = use_spell_slot(p.id, 1)
        assert result is False

    def test_use_spell_slot_invalid_level(self, player):
        p, game = player
        assert use_spell_slot(p.id, 0) is False
        assert use_spell_slot(p.id, 10) is False

    def test_restore_spell_slots(self, player):
        p, game = player
        create_spell_slots(player_id=p.id, level_1=0, max_level_1=2, level_2=0, max_level_2=1)

        restore_spell_slots(p.id)

        slots = get_spell_slots(p.id)
        assert slots.level_1 == 2
        assert slots.level_2 == 1

    def test_get_nonexistent(self, player):
        p, game = player
        slots = get_spell_slots(p.id)
        assert slots is None


class TestPlayerAttributes:

    def test_get_attributes(self, player):
        p, game = player
        attrs = get_player_attributes(p.id)
        assert attrs["strength"] == 16
        assert attrs["dexterity"] == 12
        assert attrs["constitution"] == 14
        assert attrs["intelligence"] == 10  # default

    def test_update_attributes(self, player):
        p, game = player
        update_player_attributes(p.id, strength=18, wisdom=14)

        attrs = get_player_attributes(p.id)
        assert attrs["strength"] == 18
        assert attrs["wisdom"] == 14
        assert attrs["dexterity"] == 12  # unchanged

    def test_update_ignores_invalid(self, player):
        p, game = player
        update_player_attributes(p.id, strength=18, bogus_attr=99)

        attrs = get_player_attributes(p.id)
        assert attrs["strength"] == 18
