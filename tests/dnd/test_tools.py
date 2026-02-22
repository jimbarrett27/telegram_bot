"""Tests for D&D DM tools."""

import pytest
from sqlalchemy import create_engine

from dnd import db_engine
from dnd.orm_models import Base
from dnd.models import CharacterClass, EventType
from dnd.database import create_game, add_player, update_game_status, update_game_adventure
from dnd.models import GameStatus
from dnd.tools import _parse_and_roll, DMTools


@pytest.fixture
def temp_db():
    """Create a temporary in-memory database for testing."""
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)
    db_engine.set_engine(test_engine)
    yield test_engine
    db_engine.reset_engine()


@pytest.fixture
def game_with_players(temp_db):
    """Create a game with two players for testing."""
    game = create_game(chat_id=12345)
    update_game_status(game.id, GameStatus.ACTIVE)
    update_game_adventure(game.id, "Test adventure text")

    p1 = add_player(
        game_id=game.id,
        telegram_user_id=100,
        telegram_username="alice",
        character_name="Aragorn",
        character_class=CharacterClass.WARRIOR,
    )
    p2 = add_player(
        game_id=game.id,
        telegram_user_id=200,
        telegram_username="bob",
        character_name="Gandalf",
        character_class=CharacterClass.MAGE,
    )
    return game


class TestDiceParser:
    """Tests for dice notation parsing and rolling."""

    def test_simple_d20(self):
        rolls, modifier, total = _parse_and_roll("1d20")
        assert len(rolls) == 1
        assert 1 <= rolls[0] <= 20
        assert modifier == 0
        assert total == rolls[0]

    def test_multiple_dice(self):
        rolls, modifier, total = _parse_and_roll("3d6")
        assert len(rolls) == 3
        assert all(1 <= r <= 6 for r in rolls)
        assert modifier == 0
        assert total == sum(rolls)

    def test_positive_modifier(self):
        rolls, modifier, total = _parse_and_roll("1d20+5")
        assert len(rolls) == 1
        assert modifier == 5
        assert total == rolls[0] + 5

    def test_negative_modifier(self):
        rolls, modifier, total = _parse_and_roll("2d6-1")
        assert len(rolls) == 2
        assert modifier == -1
        assert total == sum(rolls) - 1

    def test_whitespace_handling(self):
        rolls, modifier, total = _parse_and_roll("  1d20 + 3  ")
        # After stripping/replacing spaces: "1d20+3"
        assert modifier == 3

    def test_case_insensitive(self):
        rolls, modifier, total = _parse_and_roll("1D20")
        assert len(rolls) == 1

    def test_invalid_notation(self):
        with pytest.raises(ValueError, match="Invalid dice notation"):
            _parse_and_roll("abc")

    def test_invalid_no_d(self):
        with pytest.raises(ValueError, match="Invalid dice notation"):
            _parse_and_roll("20")

    def test_too_many_dice(self):
        with pytest.raises(ValueError, match="between 1 and 100"):
            _parse_and_roll("101d6")

    def test_too_many_sides(self):
        with pytest.raises(ValueError, match="between 2 and 100"):
            _parse_and_roll("1d101")

    def test_one_sided_die(self):
        with pytest.raises(ValueError, match="between 2 and 100"):
            _parse_and_roll("1d1")


class TestDMToolsRollDice:
    """Tests for the roll_dice tool function."""

    def test_roll_dice_valid(self, temp_db):
        game = create_game(chat_id=99999)
        tools = DMTools(game.id).as_tools()
        roll_dice = tools[0]  # First tool is roll_dice

        result = roll_dice.invoke({"notation": "1d20"})
        assert "Rolled 1d20:" in result
        assert "=" in result

    def test_roll_dice_with_modifier(self, temp_db):
        game = create_game(chat_id=99998)
        tools = DMTools(game.id).as_tools()
        roll_dice = tools[0]

        result = roll_dice.invoke({"notation": "2d6+3"})
        assert "Rolled 2d6+3:" in result
        assert "+ 3 =" in result

    def test_roll_dice_invalid(self, temp_db):
        game = create_game(chat_id=99997)
        tools = DMTools(game.id).as_tools()
        roll_dice = tools[0]

        result = roll_dice.invoke({"notation": "banana"})
        assert "Invalid dice notation" in result


class TestDMToolsGetPartyStatus:
    """Tests for the get_party_status tool function."""

    def test_returns_party_info(self, game_with_players):
        tools = DMTools(game_with_players.id).as_tools()
        get_party_status = tools[1]

        result = get_party_status.invoke({})
        assert "Aragorn" in result
        assert "Warrior" in result
        assert "Gandalf" in result
        assert "Mage" in result
        assert "20/20 HP" in result

    def test_no_players(self, temp_db):
        game = create_game(chat_id=88888)
        tools = DMTools(game.id).as_tools()
        get_party_status = tools[1]

        result = get_party_status.invoke({})
        assert "No players" in result


class TestDMToolsApplyDamage:
    """Tests for the apply_damage tool function."""

    def test_apply_damage(self, game_with_players):
        tools = DMTools(game_with_players.id).as_tools()
        apply_damage = tools[2]

        result = apply_damage.invoke({
            "player_name": "Aragorn",
            "amount": -5,
            "reason": "goblin attack",
        })
        assert "takes 5 damage" in result
        assert "goblin attack" in result
        assert "20 -> 15" in result

    def test_apply_healing(self, game_with_players):
        tools = DMTools(game_with_players.id).as_tools()
        apply_damage = tools[2]

        # First damage, then heal
        apply_damage.invoke({
            "player_name": "Aragorn",
            "amount": -10,
            "reason": "test damage",
        })
        result = apply_damage.invoke({
            "player_name": "Aragorn",
            "amount": 5,
            "reason": "healing spell",
        })
        assert "heals 5 HP" in result
        assert "healing spell" in result

    def test_hp_clamp_at_zero(self, game_with_players):
        tools = DMTools(game_with_players.id).as_tools()
        apply_damage = tools[2]

        result = apply_damage.invoke({
            "player_name": "Aragorn",
            "amount": -100,
            "reason": "dragon breath",
        })
        assert "-> 0" in result

    def test_hp_clamp_at_max(self, game_with_players):
        tools = DMTools(game_with_players.id).as_tools()
        apply_damage = tools[2]

        result = apply_damage.invoke({
            "player_name": "Aragorn",
            "amount": 100,
            "reason": "divine intervention",
        })
        assert "-> 20" in result

    def test_unknown_player(self, game_with_players):
        tools = DMTools(game_with_players.id).as_tools()
        apply_damage = tools[2]

        result = apply_damage.invoke({
            "player_name": "Legolas",
            "amount": -5,
            "reason": "test",
        })
        assert "No player named 'Legolas'" in result
        assert "Aragorn" in result

    def test_case_insensitive_name(self, game_with_players):
        tools = DMTools(game_with_players.id).as_tools()
        apply_damage = tools[2]

        result = apply_damage.invoke({
            "player_name": "aragorn",
            "amount": -3,
            "reason": "test",
        })
        assert "takes 3 damage" in result


class TestDMToolsGetRecentHistory:
    """Tests for the get_recent_history tool function."""

    def test_no_events(self, game_with_players):
        tools = DMTools(game_with_players.id).as_tools()
        get_recent_history = tools[3]

        result = get_recent_history.invoke({"limit": 20})
        assert "No events" in result

    def test_with_events(self, game_with_players):
        from dnd.database import add_event

        add_event(
            game_id=game_with_players.id,
            turn_number=1,
            event_type=EventType.NARRATION,
            content="The goblins attack!",
        )
        add_event(
            game_id=game_with_players.id,
            turn_number=1,
            event_type=EventType.PLAYER_ACTION,
            content="Aragorn swings his sword",
            actor_player_id=1,
        )

        tools = DMTools(game_with_players.id).as_tools()
        get_recent_history = tools[3]

        result = get_recent_history.invoke({"limit": 20})
        assert "NARRATION" in result
        assert "goblins attack" in result
        assert "PLAYER_ACTION" in result
        assert "swings his sword" in result
