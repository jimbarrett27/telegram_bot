from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, Text, UniqueConstraint, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from util.timezone import stockholm_now


class Base(DeclarativeBase):
    pass


# Status constants
GAME_LOBBY = "lobby"
GAME_ACTIVE = "active"
GAME_PAUSED = "paused"
GAME_FINISHED = "finished"

ROUND_IN_PROGRESS = "in_progress"
ROUND_RESOLVED = "resolved"


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(Text, default=GAME_LOBBY)
    current_round_number: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=stockholm_now)

    players: Mapped[list["Player"]] = relationship(back_populates="game", order_by="Player.join_order")
    rounds: Mapped[list["Round"]] = relationship(back_populates="game", order_by="Round.round_number")


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("game_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    user_id: Mapped[int] = mapped_column(Integer)
    display_name: Mapped[str] = mapped_column(Text)
    character_class: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    character_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    join_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(default=stockholm_now)

    game: Mapped["Game"] = relationship(back_populates="players")


class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    round_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, default=ROUND_IN_PROGRESS)
    narrative: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=stockholm_now)

    game: Mapped["Game"] = relationship(back_populates="rounds")
    actions: Mapped[list["Action"]] = relationship(back_populates="round")


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    text: Mapped[str] = mapped_column(Text)
    outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(default=stockholm_now)

    round: Mapped["Round"] = relationship(back_populates="actions")
    player: Mapped["Player"] = relationship()
