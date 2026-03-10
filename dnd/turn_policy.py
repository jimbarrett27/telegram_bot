from abc import ABC, abstractmethod
from typing import Optional

from dnd.models import Player, Action


class TurnPolicy(ABC):
    @abstractmethod
    def get_current_player(self, players: list[Player], actions: list[Action]) -> Optional[Player]:
        """Return the player whose turn it is, or None if the round is complete."""

    @abstractmethod
    def is_round_complete(self, players: list[Player], actions: list[Action]) -> bool:
        """Return True if all players have acted this round."""


class RoundRobinPolicy(TurnPolicy):
    def get_current_player(self, players: list[Player], actions: list[Action]) -> Optional[Player]:
        acted_player_ids = {a.player_id for a in actions}
        for player in players:
            if player.id not in acted_player_ids:
                return player
        return None

    def is_round_complete(self, players: list[Player], actions: list[Action]) -> bool:
        acted_player_ids = {a.player_id for a in actions}
        return all(p.id in acted_player_ids for p in players)
