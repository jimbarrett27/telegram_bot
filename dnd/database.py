from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from dnd.db_engine import get_engine, get_session
from dnd.models import (
    Base,
    Game, Player, Round, Action,
    GAME_LOBBY, GAME_ACTIVE, GAME_PAUSED, GAME_FINISHED,
    ROUND_IN_PROGRESS, ROUND_RESOLVED,
)
from util.timezone import stockholm_now


def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)


def get_active_game(chat_id: int) -> Optional[Game]:
    with get_session() as session:
        stmt = select(Game).where(
            Game.chat_id == chat_id,
            Game.status.in_([GAME_LOBBY, GAME_ACTIVE, GAME_PAUSED]),
        )
        game = session.execute(stmt).scalar_one_or_none()
        if game:
            session.expunge(game)
        return game


def create_game(chat_id: int) -> Game:
    with get_session() as session:
        existing = session.execute(
            select(Game).where(
                Game.chat_id == chat_id,
                Game.status.in_([GAME_LOBBY, GAME_ACTIVE, GAME_PAUSED]),
            )
        ).scalar_one_or_none()
        if existing:
            raise ValueError("There's already an active game in this chat.")

        game = Game(chat_id=chat_id, status=GAME_LOBBY)
        session.add(game)
        session.flush()
        session.expunge(game)
        return game


def add_player(
    game_id: int,
    user_id: int,
    display_name: str,
    character_class: Optional[str] = None,
    character_description: Optional[str] = None,
) -> tuple[Player, bool]:
    """Add a player. Returns (player, is_new). If already joined, returns existing."""
    with get_session() as session:
        existing = session.execute(
            select(Player).where(Player.game_id == game_id, Player.user_id == user_id)
        ).scalar_one_or_none()
        if existing:
            session.expunge(existing)
            return existing, False

        max_order = session.execute(
            select(Player.join_order).where(Player.game_id == game_id).order_by(Player.join_order.desc())
        ).scalar()
        next_order = (max_order or 0) + 1

        player = Player(
            game_id=game_id,
            user_id=user_id,
            display_name=display_name,
            character_class=character_class,
            character_description=character_description,
            join_order=next_order,
        )
        session.add(player)
        session.flush()
        session.expunge(player)
        return player, True


def get_players(game_id: int) -> list[Player]:
    with get_session() as session:
        stmt = select(Player).where(Player.game_id == game_id).order_by(Player.join_order)
        players = list(session.execute(stmt).scalars().all())
        for p in players:
            session.expunge(p)
        return players


def get_player_by_user_id(game_id: int, user_id: int) -> Optional[Player]:
    with get_session() as session:
        stmt = select(Player).where(Player.game_id == game_id, Player.user_id == user_id)
        player = session.execute(stmt).scalar_one_or_none()
        if player:
            session.expunge(player)
        return player


def start_game(game_id: int) -> Round:
    with get_session() as session:
        game = session.get(Game, game_id)
        game.status = GAME_ACTIVE
        game.current_round_number = 1

        round_ = Round(game_id=game_id, round_number=1, status=ROUND_IN_PROGRESS)
        session.add(round_)
        session.flush()
        session.expunge(round_)
        return round_


def get_current_round(game_id: int) -> Optional[Round]:
    with get_session() as session:
        game = session.get(Game, game_id)
        if not game:
            return None
        stmt = select(Round).where(
            Round.game_id == game_id,
            Round.round_number == game.current_round_number,
        )
        round_ = session.execute(stmt).scalar_one_or_none()
        if round_:
            session.expunge(round_)
        return round_


def set_round_narrative(round_id: int, narrative: str):
    with get_session() as session:
        round_ = session.get(Round, round_id)
        round_.narrative = narrative


def submit_action(round_id: int, player_id: int, text: str) -> Action:
    with get_session() as session:
        action = Action(
            round_id=round_id,
            player_id=player_id,
            text=text,
            submitted_at=stockholm_now(),
        )
        session.add(action)
        session.flush()
        session.expunge(action)
        return action


def set_action_outcome(action_id: int, outcome: str) -> None:
    with get_session() as session:
        action = session.get(Action, action_id)
        action.outcome = outcome


def get_actions_for_round(round_id: int) -> list[Action]:
    with get_session() as session:
        stmt = select(Action).where(Action.round_id == round_id).order_by(Action.submitted_at)
        actions = list(session.execute(stmt).scalars().all())
        for a in actions:
            session.expunge(a)
        return actions


def resolve_round(round_id: int, resolution_text: str):
    with get_session() as session:
        round_ = session.get(Round, round_id)
        round_.status = ROUND_RESOLVED
        round_.resolution = resolution_text


def advance_round(game_id: int) -> Round:
    with get_session() as session:
        game = session.get(Game, game_id)
        game.current_round_number += 1

        round_ = Round(
            game_id=game_id,
            round_number=game.current_round_number,
            status=ROUND_IN_PROGRESS,
        )
        session.add(round_)
        session.flush()
        session.expunge(round_)
        return round_


def finish_game(game_id: int):
    with get_session() as session:
        game = session.get(Game, game_id)
        game.status = GAME_FINISHED


def get_all_rounds(game_id: int) -> list[Round]:
    with get_session() as session:
        stmt = select(Round).where(Round.game_id == game_id).order_by(Round.round_number)
        rounds = list(session.execute(stmt).scalars().all())
        for r in rounds:
            session.expunge(r)
        return rounds
