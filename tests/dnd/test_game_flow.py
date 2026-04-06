"""End-to-end tests for the D&D game flow."""

import pytest
from sqlalchemy import create_engine

from dnd import database as db
from dnd import db_engine
from dnd.game_manager import GameManager, NoActiveGame, NotYourTurn
from dnd.models import Base, GAME_ACTIVE, GAME_LOBBY


class FakeNarrator:
    """Deterministic narrator that never calls the LLM."""

    async def narrate_scene(self, players, story_so_far=None):
        names = ", ".join(p.name for p in players)
        return f"Scene opens. Players: {names}."

    async def evaluate_and_resolve_action(self, player, scene_narrative, action_text, recent_actions=None):
        outcome = f"{player.name} acts: {action_text}"
        return outcome, None


@pytest.fixture(autouse=True)
def temp_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db_engine.set_engine(engine)
    yield
    db_engine.reset_engine()


def make_manager():
    return GameManager(narrator=FakeNarrator())


@pytest.mark.asyncio
async def test_full_two_player_round():
    manager = make_manager()

    game = manager.create_game(chat_id=1)
    assert game.status == GAME_LOBBY

    p1, _ = manager.join_game(1, user_id=101, display_name="Alice")
    p2, _ = manager.join_game(1, user_id=102, display_name="Bob")

    narrative, first = await manager.start_game(chat_id=1)
    assert narrative
    assert first.display_name in ("Alice", "Bob")

    second_user_id = 102 if first.user_id == 101 else 101

    # First player submits
    result = await manager.submit_action(1, first.user_id, "I look around carefully.")
    assert result.accepted
    assert not result.round_complete
    assert result.outcome

    # Second player submits — completes the round
    result = await manager.submit_action(1, second_user_id, "I draw my sword.")
    assert result.accepted
    assert result.round_complete
    assert result.outcome
    assert result.resolution
    assert result.new_narrative
    assert result.next_player is not None


@pytest.mark.asyncio
async def test_wrong_turn_raises():
    manager = make_manager()
    manager.create_game(chat_id=1)
    manager.join_game(1, user_id=101, display_name="Alice")
    manager.join_game(1, user_id=102, display_name="Bob")

    _, first = await manager.start_game(chat_id=1)
    wrong_user_id = 102 if first.user_id == 101 else 101

    with pytest.raises(NotYourTurn):
        await manager.submit_action(1, wrong_user_id, "I act out of turn!")


@pytest.mark.asyncio
async def test_no_active_game_raises():
    manager = make_manager()
    with pytest.raises(NoActiveGame):
        await manager.submit_action(chat_id=999, user_id=101, action_text="anything")


@pytest.mark.asyncio
async def test_get_story_after_round():
    manager = make_manager()
    manager.create_game(chat_id=1)
    manager.join_game(1, user_id=101, display_name="Alice")
    manager.join_game(1, user_id=102, display_name="Bob")

    _, first = await manager.start_game(chat_id=1)
    second_user_id = 102 if first.user_id == 101 else 101

    await manager.submit_action(1, first.user_id, "I search the room.")
    await manager.submit_action(1, second_user_id, "I stand guard.")

    story = manager.get_story(chat_id=1)
    assert len(story) > 0


@pytest.mark.asyncio
async def test_single_player_game():
    """A single player's action completes the round immediately."""
    manager = make_manager()
    manager.create_game(chat_id=1)
    manager.join_game(1, user_id=101, display_name="Solo")

    _, first = await manager.start_game(chat_id=1)
    assert first.display_name == "Solo"

    result = await manager.submit_action(1, 101, "I venture forth alone.")
    assert result.accepted
    assert result.round_complete


@pytest.mark.asyncio
async def test_recent_actions_passed_to_narrator():
    """Each action sees the previously resolved actions as context."""
    seen_recent = []

    class TrackingNarrator(FakeNarrator):
        async def evaluate_and_resolve_action(self, player, scene_narrative, action_text, recent_actions=None):
            seen_recent.append(list(recent_actions or []))
            return await super().evaluate_and_resolve_action(player, scene_narrative, action_text, recent_actions)

    manager = GameManager(narrator=TrackingNarrator())
    manager.create_game(chat_id=1)
    manager.join_game(1, user_id=101, display_name="Alice")
    manager.join_game(1, user_id=102, display_name="Bob")

    _, first = await manager.start_game(chat_id=1)
    second_user_id = 102 if first.user_id == 101 else 101

    await manager.submit_action(1, first.user_id, "First action.")
    await manager.submit_action(1, second_user_id, "Second action.")

    assert len(seen_recent) == 2
    assert seen_recent[0] == []           # No prior actions for first player
    assert len(seen_recent[1]) == 1       # First player's resolved action visible to second
    assert seen_recent[1][0].player_name == first.display_name
