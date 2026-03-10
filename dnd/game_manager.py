from dataclasses import dataclass
from typing import Optional

from dnd import database as db
from dnd.models import Game, Player, Round, GAME_LOBBY, GAME_ACTIVE
from dnd.turn_policy import TurnPolicy, RoundRobinPolicy
from dnd.narrator import Narrator
from util.logging_util import setup_logger

logger = setup_logger(__name__)


class NoActiveGame(Exception):
    pass


class GameNotInLobby(Exception):
    pass


class GameNotActive(Exception):
    pass


class NotYourTurn(Exception):
    def __init__(self, current_player_name: str):
        self.current_player_name = current_player_name
        super().__init__(f"It's {current_player_name}'s turn.")


class PlayerNotInGame(Exception):
    pass


class NotEnoughPlayers(Exception):
    pass


@dataclass
class ActionResult:
    accepted: bool
    round_complete: bool
    resolution: Optional[str] = None
    new_narrative: Optional[str] = None
    next_player: Optional[Player] = None


class GameManager:
    def __init__(self, turn_policy: TurnPolicy = None, narrator: Narrator = None):
        self.policy = turn_policy or RoundRobinPolicy()
        self.narrator = narrator or Narrator()

    def create_game(self, chat_id: int) -> Game:
        return db.create_game(chat_id)

    def join_game(self, chat_id: int, user_id: int, display_name: str) -> tuple[Player, bool]:
        game = db.get_active_game(chat_id)
        if not game:
            raise NoActiveGame()
        if game.status != GAME_LOBBY:
            raise GameNotInLobby()
        return db.add_player(game.id, user_id, display_name)

    async def start_game(self, chat_id: int) -> tuple[str, Player]:
        """Start the game. Returns (narrative, first_player)."""
        game = db.get_active_game(chat_id)
        if not game:
            raise NoActiveGame()
        if game.status != GAME_LOBBY:
            raise GameNotInLobby()

        players = db.get_players(game.id)
        if not players:
            raise NotEnoughPlayers()

        round_ = db.start_game(game.id)
        narrative = await self.narrator.narrate_scene(1, None)
        db.set_round_narrative(round_.id, narrative)

        first_player = self.policy.get_current_player(players, [])
        return narrative, first_player

    def get_current_player(self, chat_id: int) -> Optional[Player]:
        game = db.get_active_game(chat_id)
        if not game or game.status != GAME_ACTIVE:
            return None

        players = db.get_players(game.id)
        round_ = db.get_current_round(game.id)
        if not round_:
            return None

        actions = db.get_actions_for_round(round_.id)
        return self.policy.get_current_player(players, actions)

    async def submit_action(self, chat_id: int, user_id: int, action_text: str) -> ActionResult:
        game = db.get_active_game(chat_id)
        if not game or game.status != GAME_ACTIVE:
            raise NoActiveGame()

        player = db.get_player_by_user_id(game.id, user_id)
        if not player:
            raise PlayerNotInGame()

        players = db.get_players(game.id)
        round_ = db.get_current_round(game.id)
        actions = db.get_actions_for_round(round_.id)

        current = self.policy.get_current_player(players, actions)
        if not current or current.id != player.id:
            raise NotYourTurn(current.display_name if current else "nobody")

        db.submit_action(round_.id, player.id, action_text)
        actions = db.get_actions_for_round(round_.id)

        if self.policy.is_round_complete(players, actions):
            action_pairs = []
            for a in actions:
                p = next((p for p in players if p.id == a.player_id), None)
                name = p.display_name if p else "Unknown"
                action_pairs.append((name, a.text))

            resolution = await self.narrator.resolve_round(round_.narrative or "", action_pairs)
            db.resolve_round(round_.id, resolution)

            new_round = db.advance_round(game.id)
            new_narrative = await self.narrator.narrate_scene(new_round.round_number, resolution)
            db.set_round_narrative(new_round.id, new_narrative)

            next_player = self.policy.get_current_player(players, [])
            return ActionResult(
                accepted=True,
                round_complete=True,
                resolution=resolution,
                new_narrative=new_narrative,
                next_player=next_player,
            )
        else:
            next_player = self.policy.get_current_player(players, actions)
            return ActionResult(
                accepted=True,
                round_complete=False,
                next_player=next_player,
            )

    async def skip_player(self, chat_id: int, player_id: int) -> Optional[ActionResult]:
        game = db.get_active_game(chat_id)
        if not game or game.status != GAME_ACTIVE:
            return None

        player = db.get_player_by_user_id(game.id, player_id) if False else None
        # Find the player by their player.id, not user_id
        players = db.get_players(game.id)
        player = next((p for p in players if p.id == player_id), None)
        if not player:
            return None

        return await self.submit_action(chat_id, player.user_id, "(skipped)")

    def get_story(self, chat_id: int) -> str:
        game = db.get_active_game(chat_id)
        if not game:
            raise NoActiveGame()

        rounds = db.get_all_rounds(game.id)
        if not rounds:
            return "No story yet."

        parts = []
        for r in rounds:
            if r.narrative:
                parts.append(r.narrative)
            if r.resolution:
                parts.append(r.resolution)
        return "\n\n---\n\n".join(parts) if parts else "No story yet."

    def get_status(self, chat_id: int) -> str:
        game = db.get_active_game(chat_id)
        if not game:
            return "No active game in this chat."

        players = db.get_players(game.id)
        player_list = "\n".join(f"  {p.join_order}. {p.display_name}" for p in players)

        if game.status == GAME_LOBBY:
            return f"Game is in lobby.\n\nPlayers:\n{player_list}\n\nWaiting for more players to join..."

        current = self.get_current_player(chat_id)
        turn_info = f"Waiting for: {current.display_name}" if current else "Round complete"

        return (
            f"Round {game.current_round_number}\n\n"
            f"Players:\n{player_list}\n\n"
            f"{turn_info}"
        )

    def get_player_info(self, chat_id: int, user_id: int) -> Optional[Player]:
        game = db.get_active_game(chat_id)
        if not game:
            return None
        return db.get_player_by_user_id(game.id, user_id)

    def finish_game(self, chat_id: int):
        game = db.get_active_game(chat_id)
        if not game:
            raise NoActiveGame()
        db.finish_game(game.id)
