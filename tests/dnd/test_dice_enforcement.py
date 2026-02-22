"""Tests for dice rolling enforcement logic."""

from unittest.mock import MagicMock

from dnd.game_logic import _extract_tools_used, _needs_dice_retry


def _make_tool_msg(name: str, content: str = "") -> MagicMock:
    """Create a mock tool message."""
    msg = MagicMock()
    msg.type = "tool"
    msg.name = name
    msg.content = content
    return msg


def _make_ai_msg(content: str = "") -> MagicMock:
    """Create a mock AI message."""
    msg = MagicMock()
    msg.type = "ai"
    msg.content = content
    return msg


class TestExtractToolsUsed:
    """Tests for _extract_tools_used helper."""

    def test_empty_messages(self):
        assert _extract_tools_used([]) == {}

    def test_no_tool_messages(self):
        messages = [_make_ai_msg("Hello")]
        assert _extract_tools_used(messages) == {}

    def test_single_tool(self):
        messages = [_make_tool_msg("roll_dice", "Rolled 1d20: [15] = 15")]
        result = _extract_tools_used(messages)
        assert result == {"roll_dice": 1}

    def test_multiple_tools(self):
        messages = [
            _make_tool_msg("roll_dice", "Rolled 1d20: [18] = 18"),
            _make_tool_msg("roll_dice", "Rolled 2d6: [3, 5] = 8"),
            _make_tool_msg("apply_damage", "Aragorn takes 8 damage"),
        ]
        result = _extract_tools_used(messages)
        assert result == {"roll_dice": 2, "apply_damage": 1}

    def test_mixed_message_types(self):
        messages = [
            _make_ai_msg("Let me roll for that."),
            _make_tool_msg("roll_dice", "Rolled 1d20: [12] = 12"),
            _make_ai_msg("The attack hits!"),
            _make_tool_msg("apply_damage", "Damage applied"),
        ]
        result = _extract_tools_used(messages)
        assert result == {"roll_dice": 1, "apply_damage": 1}

    def test_ignores_messages_without_name(self):
        msg = MagicMock()
        msg.type = "tool"
        # No name attribute
        del msg.name
        messages = [msg]
        result = _extract_tools_used(messages)
        assert result == {}


class TestNeedsDiceRetry:
    """Tests for _needs_dice_retry logic."""

    def test_no_damage_no_dice_ok(self):
        # Pure narration, no combat — no retry needed
        assert _needs_dice_retry({}) is False

    def test_dice_and_damage_ok(self):
        # Proper usage: rolled dice then applied damage
        assert _needs_dice_retry({"roll_dice": 2, "apply_damage": 1}) is False

    def test_damage_without_dice_needs_retry(self):
        # Applied damage without rolling — needs retry
        assert _needs_dice_retry({"apply_damage": 1}) is True

    def test_dice_without_damage_ok(self):
        # Rolled dice for a skill check but no damage — fine
        assert _needs_dice_retry({"roll_dice": 1}) is False

    def test_other_tools_no_damage_ok(self):
        # Used other tools but no damage
        assert _needs_dice_retry({"get_party_status": 1, "get_recent_history": 1}) is False

    def test_damage_with_other_tools_but_no_dice(self):
        # Applied damage and used other tools but no dice
        assert _needs_dice_retry({"apply_damage": 1, "get_party_status": 1}) is True

    def test_clarification_with_damage_no_dice(self):
        # Edge case: clarification + damage but no dice
        assert _needs_dice_retry({"request_clarification": 1, "apply_damage": 1}) is True
