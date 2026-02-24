"""
Database operations for the D&D game system.

Uses SQLAlchemy ORM for database access. The public API uses the dataclass
models from models.py, with conversion to/from ORM models handled internally.
"""

import time
from typing import List, Optional

from sqlalchemy import select

from dnd.db_engine import get_engine, get_session
from collections import deque

from dnd.models import (
    Game,
    Player,
    GameEvent,
    InventoryItem,
    SpellSlots,
    CampaignSection,
    DmNote,
    Zone,
    ZoneAdjacency,
    ZoneEntity,
    GameStatus,
    CharacterClass,
    EventType,
)
from dnd.orm_models import (
    Base,
    GameORM,
    PlayerORM,
    GameEventORM,
    InventoryItemORM,
    SpellSlotsORM,
    CampaignSectionORM,
    DmNoteORM,
    ZoneORM,
    ZoneAdjacencyORM,
    ZoneEntityORM,
    game_orm_to_dataclass,
    player_orm_to_dataclass,
    event_orm_to_dataclass,
    inventory_orm_to_dataclass,
    spell_slots_orm_to_dataclass,
    campaign_section_orm_to_dataclass,
    dm_note_orm_to_dataclass,
    zone_orm_to_dataclass,
    zone_adjacency_orm_to_dataclass,
    zone_entity_orm_to_dataclass,
)


def init_db():
    """Initialize the database schema."""
    engine = get_engine()
    Base.metadata.create_all(engine)


def create_game(
    chat_id: int,
    campaign_name: str = "",
    recommended_level: int = 1,
) -> Game:
    """Create a new game for a chat. Returns the created Game."""
    now = int(time.time())
    with get_session() as session:
        orm = GameORM(
            chat_id=chat_id,
            status=GameStatus.RECRUITING.value,
            adventure_text="",
            campaign_name=campaign_name,
            recommended_level=recommended_level,
            turn_number=0,
            created_at=now,
            updated_at=now,
        )
        session.add(orm)
        session.flush()
        return game_orm_to_dataclass(orm)


def get_game_by_id(game_id: int) -> Optional[Game]:
    """Get a game by its ID, including its players."""
    with get_session() as session:
        game_orm = session.get(GameORM, game_id)
        if game_orm is None:
            return None

        player_stmt = select(PlayerORM).where(PlayerORM.game_id == game_orm.id)
        player_orms = session.execute(player_stmt).scalars().all()
        players = [player_orm_to_dataclass(p) for p in player_orms]

        return game_orm_to_dataclass(game_orm, players)


def get_game_by_chat(chat_id: int) -> Optional[Game]:
    """Get a game by chat ID, including its players."""
    with get_session() as session:
        stmt = select(GameORM).where(GameORM.chat_id == chat_id)
        game_orm = session.execute(stmt).scalar_one_or_none()
        if game_orm is None:
            return None

        player_stmt = select(PlayerORM).where(PlayerORM.game_id == game_orm.id)
        player_orms = session.execute(player_stmt).scalars().all()
        players = [player_orm_to_dataclass(p) for p in player_orms]

        return game_orm_to_dataclass(game_orm, players)


def add_player(
    game_id: int,
    telegram_user_id: int,
    telegram_username: str,
    character_name: str,
    character_class: CharacterClass,
    hp: int = 20,
    max_hp: int = 20,
    strength: int = 10,
    dexterity: int = 10,
    constitution: int = 10,
    intelligence: int = 10,
    wisdom: int = 10,
    charisma: int = 10,
    is_ai: bool = False,
    level: int = 1,
) -> Player:
    """Add a player to a game. Returns the created Player."""
    now = int(time.time())
    with get_session() as session:
        orm = PlayerORM(
            game_id=game_id,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            character_name=character_name,
            character_class=character_class.value,
            hp=hp,
            max_hp=max_hp,
            level=level,
            strength=strength,
            dexterity=dexterity,
            constitution=constitution,
            intelligence=intelligence,
            wisdom=wisdom,
            charisma=charisma,
            is_ai=int(is_ai),
            joined_at=now,
        )
        session.add(orm)
        session.flush()
        return player_orm_to_dataclass(orm)


def get_player_by_user(game_id: int, telegram_user_id: int) -> Optional[Player]:
    """Get a player by game ID and Telegram user ID."""
    with get_session() as session:
        stmt = select(PlayerORM).where(
            PlayerORM.game_id == game_id,
            PlayerORM.telegram_user_id == telegram_user_id,
        )
        orm = session.execute(stmt).scalar_one_or_none()
        if orm is None:
            return None
        return player_orm_to_dataclass(orm)


def get_player_by_id(player_id: int) -> Optional[Player]:
    """Get a player by ID."""
    with get_session() as session:
        orm = session.get(PlayerORM, player_id)
        if orm is None:
            return None
        return player_orm_to_dataclass(orm)


def update_player_hp(player_id: int, hp: int):
    """Update a player's HP."""
    with get_session() as session:
        orm = session.get(PlayerORM, player_id)
        if orm is not None:
            orm.hp = max(0, hp)


def update_game_status(game_id: int, status: GameStatus):
    """Update a game's status."""
    now = int(time.time())
    with get_session() as session:
        orm = session.get(GameORM, game_id)
        if orm is not None:
            orm.status = status.value
            orm.updated_at = now


def update_game_adventure(game_id: int, adventure_text: str):
    """Set the adventure text for a game."""
    now = int(time.time())
    with get_session() as session:
        orm = session.get(GameORM, game_id)
        if orm is not None:
            orm.adventure_text = adventure_text
            orm.updated_at = now


def update_game_current_player(game_id: int, player_id: Optional[int], turn_number: int):
    """Update the current player and turn number."""
    now = int(time.time())
    with get_session() as session:
        orm = session.get(GameORM, game_id)
        if orm is not None:
            orm.current_player_id = player_id
            orm.turn_number = turn_number
            orm.updated_at = now


def add_event(
    game_id: int,
    turn_number: int,
    event_type: EventType,
    content: str,
    actor_player_id: Optional[int] = None,
) -> GameEvent:
    """Add a game event. Returns the created GameEvent."""
    now = int(time.time())
    with get_session() as session:
        orm = GameEventORM(
            game_id=game_id,
            turn_number=turn_number,
            event_type=event_type.value,
            actor_player_id=actor_player_id,
            content=content,
            created_at=now,
        )
        session.add(orm)
        session.flush()
        return event_orm_to_dataclass(orm)


def get_recent_events(game_id: int, limit: int = 30) -> List[GameEvent]:
    """Get the most recent events for a game."""
    with get_session() as session:
        stmt = (
            select(GameEventORM)
            .where(GameEventORM.game_id == game_id)
            .order_by(GameEventORM.id.desc())
            .limit(limit)
        )
        orms = session.execute(stmt).scalars().all()
        events = [event_orm_to_dataclass(orm) for orm in orms]
        events.reverse()  # Return in chronological order
        return events


def delete_game(chat_id: int):
    """Delete a game and all related data for a chat."""
    with get_session() as session:
        stmt = select(GameORM).where(GameORM.chat_id == chat_id)
        game_orm = session.execute(stmt).scalar_one_or_none()
        if game_orm is None:
            return

        # Delete zone entities
        ze_stmt = select(ZoneEntityORM).where(ZoneEntityORM.game_id == game_orm.id)
        for ze in session.execute(ze_stmt).scalars().all():
            session.delete(ze)

        # Delete zone adjacencies (via zones)
        z_stmt = select(ZoneORM).where(ZoneORM.game_id == game_orm.id)
        zone_orms = session.execute(z_stmt).scalars().all()
        for zone in zone_orms:
            za_stmt = select(ZoneAdjacencyORM).where(
                (ZoneAdjacencyORM.zone_a_id == zone.id)
                | (ZoneAdjacencyORM.zone_b_id == zone.id)
            )
            for za in session.execute(za_stmt).scalars().all():
                session.delete(za)

        # Delete zones
        for zone in zone_orms:
            session.delete(zone)

        # Delete DM notes
        dn_stmt = select(DmNoteORM).where(DmNoteORM.game_id == game_orm.id)
        for dn in session.execute(dn_stmt).scalars().all():
            session.delete(dn)

        # Delete campaign sections
        cs_stmt = select(CampaignSectionORM).where(CampaignSectionORM.game_id == game_orm.id)
        for cs in session.execute(cs_stmt).scalars().all():
            session.delete(cs)

        # Delete inventory items
        inv_stmt = select(InventoryItemORM).where(InventoryItemORM.game_id == game_orm.id)
        for item in session.execute(inv_stmt).scalars().all():
            session.delete(item)

        # Delete spell slots (via players)
        player_stmt = select(PlayerORM).where(PlayerORM.game_id == game_orm.id)
        player_orms = session.execute(player_stmt).scalars().all()
        for player in player_orms:
            ss_stmt = select(SpellSlotsORM).where(SpellSlotsORM.player_id == player.id)
            for ss in session.execute(ss_stmt).scalars().all():
                session.delete(ss)

        # Delete events
        event_stmt = select(GameEventORM).where(GameEventORM.game_id == game_orm.id)
        for event in session.execute(event_stmt).scalars().all():
            session.delete(event)

        # Delete players
        for player in player_orms:
            session.delete(player)

        # Delete game
        session.delete(game_orm)


# --- Inventory operations ---


def add_inventory_item(
    player_id: int,
    game_id: int,
    item_name: str,
    item_type: str = "gear",
    quantity: int = 1,
    equipped: bool = False,
    properties: Optional[str] = None,
) -> InventoryItem:
    """Add an item to a player's inventory."""
    now = int(time.time())
    with get_session() as session:
        orm = InventoryItemORM(
            player_id=player_id,
            game_id=game_id,
            item_name=item_name,
            item_type=item_type,
            quantity=quantity,
            equipped=int(equipped),
            properties=properties,
            created_at=now,
        )
        session.add(orm)
        session.flush()
        return inventory_orm_to_dataclass(orm)


def get_player_inventory(player_id: int) -> List[InventoryItem]:
    """Get all inventory items for a player."""
    with get_session() as session:
        stmt = select(InventoryItemORM).where(InventoryItemORM.player_id == player_id)
        orms = session.execute(stmt).scalars().all()
        return [inventory_orm_to_dataclass(orm) for orm in orms]


def update_inventory_item_quantity(item_id: int, quantity: int):
    """Update the quantity of an inventory item. Deletes if quantity <= 0."""
    with get_session() as session:
        orm = session.get(InventoryItemORM, item_id)
        if orm is None:
            return
        if quantity <= 0:
            session.delete(orm)
        else:
            orm.quantity = quantity


def update_inventory_item_equipped(item_id: int, equipped: bool):
    """Set an inventory item's equipped state."""
    with get_session() as session:
        orm = session.get(InventoryItemORM, item_id)
        if orm is not None:
            orm.equipped = int(equipped)


def remove_inventory_item_by_name(player_id: int, item_name: str, quantity: int = 1) -> bool:
    """Remove quantity of an item from a player's inventory by name.

    Returns True if the item was found and removed/decremented, False otherwise.
    """
    with get_session() as session:
        stmt = select(InventoryItemORM).where(
            InventoryItemORM.player_id == player_id,
            InventoryItemORM.item_name == item_name,
        )
        orm = session.execute(stmt).scalar_one_or_none()
        if orm is None:
            return False
        new_qty = orm.quantity - quantity
        if new_qty <= 0:
            session.delete(orm)
        else:
            orm.quantity = new_qty
        return True


# --- Spell slot operations ---


def create_spell_slots(player_id: int, **slot_values) -> SpellSlots:
    """Create spell slots for a player. Pass level_N and max_level_N kwargs."""
    with get_session() as session:
        orm = SpellSlotsORM(player_id=player_id, **slot_values)
        session.add(orm)
        session.flush()
        return spell_slots_orm_to_dataclass(orm)


def get_spell_slots(player_id: int) -> Optional[SpellSlots]:
    """Get spell slots for a player."""
    with get_session() as session:
        stmt = select(SpellSlotsORM).where(SpellSlotsORM.player_id == player_id)
        orm = session.execute(stmt).scalar_one_or_none()
        if orm is None:
            return None
        return spell_slots_orm_to_dataclass(orm)


def use_spell_slot(player_id: int, level: int) -> bool:
    """Consume one spell slot of the given level. Returns True if successful."""
    if level < 1 or level > 9:
        return False
    col_name = f"level_{level}"
    with get_session() as session:
        stmt = select(SpellSlotsORM).where(SpellSlotsORM.player_id == player_id)
        orm = session.execute(stmt).scalar_one_or_none()
        if orm is None:
            return False
        current = getattr(orm, col_name)
        if current <= 0:
            return False
        setattr(orm, col_name, current - 1)
        return True


def restore_spell_slots(player_id: int):
    """Restore all spell slots to max (long rest)."""
    with get_session() as session:
        stmt = select(SpellSlotsORM).where(SpellSlotsORM.player_id == player_id)
        orm = session.execute(stmt).scalar_one_or_none()
        if orm is None:
            return
        for lvl in range(1, 10):
            setattr(orm, f"level_{lvl}", getattr(orm, f"max_level_{lvl}"))


# --- Player attribute operations ---


def get_player_attributes(player_id: int) -> Optional[dict]:
    """Get a player's ability scores as a dict."""
    with get_session() as session:
        orm = session.get(PlayerORM, player_id)
        if orm is None:
            return None
        return {
            "strength": orm.strength,
            "dexterity": orm.dexterity,
            "constitution": orm.constitution,
            "intelligence": orm.intelligence,
            "wisdom": orm.wisdom,
            "charisma": orm.charisma,
        }


def update_player_attributes(player_id: int, **attrs):
    """Update a player's ability scores. Pass attribute_name=value kwargs."""
    valid_attrs = {"strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"}
    with get_session() as session:
        orm = session.get(PlayerORM, player_id)
        if orm is None:
            return
        for attr, value in attrs.items():
            if attr in valid_attrs:
                setattr(orm, attr, value)


# --- Campaign section operations ---


def store_campaign_sections(game_id: int, sections: list[dict]) -> list[CampaignSection]:
    """Store parsed campaign sections for a game.

    Args:
        game_id: The game ID.
        sections: List of {"title": str, "content": str} dicts.

    Returns:
        List of created CampaignSection dataclasses.
    """
    now = int(time.time())
    results = []
    with get_session() as session:
        for i, section in enumerate(sections):
            orm = CampaignSectionORM(
                game_id=game_id,
                section_title=section["title"],
                section_content=section["content"],
                section_order=i,
                created_at=now,
            )
            session.add(orm)
            session.flush()
            results.append(campaign_section_orm_to_dataclass(orm))
    return results


def get_campaign_sections(game_id: int) -> List[CampaignSection]:
    """Get all campaign sections for a game, ordered by section_order."""
    with get_session() as session:
        stmt = (
            select(CampaignSectionORM)
            .where(CampaignSectionORM.game_id == game_id)
            .order_by(CampaignSectionORM.section_order)
        )
        orms = session.execute(stmt).scalars().all()
        return [campaign_section_orm_to_dataclass(orm) for orm in orms]


def search_campaign_sections(game_id: int, query: str) -> List[CampaignSection]:
    """Search campaign sections by keyword in title or content.

    Returns matching sections ordered by section_order.
    """
    query_lower = query.lower()
    with get_session() as session:
        stmt = (
            select(CampaignSectionORM)
            .where(CampaignSectionORM.game_id == game_id)
            .order_by(CampaignSectionORM.section_order)
        )
        orms = session.execute(stmt).scalars().all()
        matches = []
        for orm in orms:
            if (query_lower in orm.section_title.lower()
                    or query_lower in orm.section_content.lower()):
                matches.append(campaign_section_orm_to_dataclass(orm))
        return matches


# --- DM note operations ---


def add_dm_note(game_id: int, content: str) -> DmNote:
    """Add a DM note for a game."""
    now = int(time.time())
    with get_session() as session:
        orm = DmNoteORM(
            game_id=game_id,
            content=content,
            created_at=now,
        )
        session.add(orm)
        session.flush()
        return dm_note_orm_to_dataclass(orm)


def get_dm_notes(game_id: int) -> List[DmNote]:
    """Get all DM notes for a game, ordered by creation time."""
    with get_session() as session:
        stmt = (
            select(DmNoteORM)
            .where(DmNoteORM.game_id == game_id)
            .order_by(DmNoteORM.id)
        )
        orms = session.execute(stmt).scalars().all()
        return [dm_note_orm_to_dataclass(orm) for orm in orms]


# --- Story summary operations ---


def get_story_summary(game_id: int) -> str:
    """Get the story summary for a game."""
    with get_session() as session:
        orm = session.get(GameORM, game_id)
        if orm is None:
            return ""
        return orm.story_summary or ""


def update_story_summary(game_id: int, summary: str):
    """Update the story summary for a game."""
    now = int(time.time())
    with get_session() as session:
        orm = session.get(GameORM, game_id)
        if orm is not None:
            orm.story_summary = summary
            orm.updated_at = now


# --- Turn timeout operations ---


def get_stale_active_games(timeout_seconds: int = 86400) -> List[Game]:
    """Find active games where the current turn has been idle too long.

    Args:
        timeout_seconds: How many seconds of inactivity before a turn is stale.
            Defaults to 86400 (24 hours).

    Returns:
        List of Game objects (with players) that have timed out.
    """
    cutoff = int(time.time()) - timeout_seconds
    with get_session() as session:
        stmt = select(GameORM).where(
            GameORM.status == GameStatus.ACTIVE.value,
            GameORM.updated_at <= cutoff,
        )
        game_orms = session.execute(stmt).scalars().all()
        results = []
        for game_orm in game_orms:
            player_stmt = select(PlayerORM).where(PlayerORM.game_id == game_orm.id)
            player_orms = session.execute(player_stmt).scalars().all()
            players = [player_orm_to_dataclass(p) for p in player_orms]
            results.append(game_orm_to_dataclass(game_orm, players))
        return results


# --- Zone operations ---


def create_zone(game_id: int, name: str, description: str = "") -> Zone:
    """Create a zone in a game."""
    now = int(time.time())
    with get_session() as session:
        orm = ZoneORM(
            game_id=game_id,
            name=name,
            description=description,
            created_at=now,
        )
        session.add(orm)
        session.flush()
        return zone_orm_to_dataclass(orm)


def get_zones(game_id: int) -> List[Zone]:
    """Get all zones for a game."""
    with get_session() as session:
        stmt = select(ZoneORM).where(ZoneORM.game_id == game_id).order_by(ZoneORM.id)
        orms = session.execute(stmt).scalars().all()
        return [zone_orm_to_dataclass(orm) for orm in orms]


def get_zone_by_name(game_id: int, name: str) -> Optional[Zone]:
    """Get a zone by name (case-insensitive)."""
    with get_session() as session:
        stmt = select(ZoneORM).where(ZoneORM.game_id == game_id)
        orms = session.execute(stmt).scalars().all()
        name_lower = name.lower()
        for orm in orms:
            if orm.name.lower() == name_lower:
                return zone_orm_to_dataclass(orm)
        return None


def delete_zone(zone_id: int):
    """Delete a zone and cascade to adjacencies and entities."""
    with get_session() as session:
        # Delete entities in this zone
        ze_stmt = select(ZoneEntityORM).where(ZoneEntityORM.zone_id == zone_id)
        for ze in session.execute(ze_stmt).scalars().all():
            session.delete(ze)

        # Delete adjacencies involving this zone
        za_stmt = select(ZoneAdjacencyORM).where(
            (ZoneAdjacencyORM.zone_a_id == zone_id)
            | (ZoneAdjacencyORM.zone_b_id == zone_id)
        )
        for za in session.execute(za_stmt).scalars().all():
            session.delete(za)

        # Delete zone
        orm = session.get(ZoneORM, zone_id)
        if orm is not None:
            session.delete(orm)


def clear_zones(game_id: int):
    """Delete all zones, adjacencies, and entities for a game."""
    with get_session() as session:
        # Delete entities
        ze_stmt = select(ZoneEntityORM).where(ZoneEntityORM.game_id == game_id)
        for ze in session.execute(ze_stmt).scalars().all():
            session.delete(ze)

        # Delete adjacencies (via zones)
        z_stmt = select(ZoneORM).where(ZoneORM.game_id == game_id)
        zone_orms = session.execute(z_stmt).scalars().all()
        for zone in zone_orms:
            za_stmt = select(ZoneAdjacencyORM).where(
                (ZoneAdjacencyORM.zone_a_id == zone.id)
                | (ZoneAdjacencyORM.zone_b_id == zone.id)
            )
            for za in session.execute(za_stmt).scalars().all():
                session.delete(za)

        # Delete zones
        for zone in zone_orms:
            session.delete(zone)


def add_zone_adjacency(zone_a_id: int, zone_b_id: int) -> ZoneAdjacency:
    """Add an adjacency between two zones. Stores smaller ID first."""
    a, b = min(zone_a_id, zone_b_id), max(zone_a_id, zone_b_id)
    with get_session() as session:
        orm = ZoneAdjacencyORM(zone_a_id=a, zone_b_id=b)
        session.add(orm)
        session.flush()
        return zone_adjacency_orm_to_dataclass(orm)


def get_adjacent_zones(zone_id: int) -> List[Zone]:
    """Get all zones adjacent to the given zone (bidirectional)."""
    with get_session() as session:
        stmt = select(ZoneAdjacencyORM).where(
            (ZoneAdjacencyORM.zone_a_id == zone_id)
            | (ZoneAdjacencyORM.zone_b_id == zone_id)
        )
        adj_orms = session.execute(stmt).scalars().all()
        neighbor_ids = set()
        for adj in adj_orms:
            if adj.zone_a_id == zone_id:
                neighbor_ids.add(adj.zone_b_id)
            else:
                neighbor_ids.add(adj.zone_a_id)

        zones = []
        for nid in neighbor_ids:
            z_orm = session.get(ZoneORM, nid)
            if z_orm is not None:
                zones.append(zone_orm_to_dataclass(z_orm))
        return zones


def get_zone_distance(game_id: int, zone_a_name: str, zone_b_name: str) -> Optional[int]:
    """BFS shortest path between two zones by name. Returns hop count or None if unreachable."""
    with get_session() as session:
        # Get all zones for this game
        z_stmt = select(ZoneORM).where(ZoneORM.game_id == game_id)
        zone_orms = session.execute(z_stmt).scalars().all()

        name_to_id = {}
        for z in zone_orms:
            name_to_id[z.name.lower()] = z.id

        start_id = name_to_id.get(zone_a_name.lower())
        end_id = name_to_id.get(zone_b_name.lower())
        if start_id is None or end_id is None:
            return None
        if start_id == end_id:
            return 0

        # Build adjacency map
        all_zone_ids = set(name_to_id.values())
        adj_map: dict[int, set[int]] = {zid: set() for zid in all_zone_ids}

        for zid in all_zone_ids:
            adj_stmt = select(ZoneAdjacencyORM).where(
                (ZoneAdjacencyORM.zone_a_id == zid)
                | (ZoneAdjacencyORM.zone_b_id == zid)
            )
            for adj in session.execute(adj_stmt).scalars().all():
                other = adj.zone_b_id if adj.zone_a_id == zid else adj.zone_a_id
                if other in all_zone_ids:
                    adj_map[zid].add(other)

        # BFS
        visited = {start_id}
        queue = deque([(start_id, 0)])
        while queue:
            current, dist = queue.popleft()
            for neighbor in adj_map.get(current, set()):
                if neighbor == end_id:
                    return dist + 1
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))

        return None


def place_entity_in_zone(
    zone_id: int,
    game_id: int,
    name: str,
    player_id: Optional[int] = None,
    entity_type: str = "npc",
) -> ZoneEntity:
    """Place an entity in a zone. Removes from previous zone first."""
    now = int(time.time())
    with get_session() as session:
        # Remove existing placement
        existing = select(ZoneEntityORM).where(
            ZoneEntityORM.game_id == game_id,
            ZoneEntityORM.name == name,
        )
        for e in session.execute(existing).scalars().all():
            session.delete(e)
        session.flush()

        orm = ZoneEntityORM(
            zone_id=zone_id,
            game_id=game_id,
            name=name,
            player_id=player_id,
            entity_type=entity_type,
            created_at=now,
        )
        session.add(orm)
        session.flush()
        return zone_entity_orm_to_dataclass(orm)


def remove_entity_from_zones(game_id: int, name: str):
    """Remove all zone placements for an entity."""
    with get_session() as session:
        stmt = select(ZoneEntityORM).where(
            ZoneEntityORM.game_id == game_id,
            ZoneEntityORM.name == name,
        )
        for e in session.execute(stmt).scalars().all():
            session.delete(e)


def get_zone_occupants(zone_id: int) -> List[ZoneEntity]:
    """Get all entities in a zone."""
    with get_session() as session:
        stmt = select(ZoneEntityORM).where(ZoneEntityORM.zone_id == zone_id)
        orms = session.execute(stmt).scalars().all()
        return [zone_entity_orm_to_dataclass(orm) for orm in orms]


def get_entity_zone(game_id: int, name: str) -> Optional[Zone]:
    """Get the zone an entity is in."""
    with get_session() as session:
        stmt = select(ZoneEntityORM).where(
            ZoneEntityORM.game_id == game_id,
            ZoneEntityORM.name == name,
        )
        entity_orm = session.execute(stmt).scalar_one_or_none()
        if entity_orm is None:
            return None
        zone_orm = session.get(ZoneORM, entity_orm.zone_id)
        if zone_orm is None:
            return None
        return zone_orm_to_dataclass(zone_orm)


def get_all_zone_entities(game_id: int) -> List[ZoneEntity]:
    """Get all entities placed in zones for a game."""
    with get_session() as session:
        stmt = select(ZoneEntityORM).where(ZoneEntityORM.game_id == game_id)
        orms = session.execute(stmt).scalars().all()
        return [zone_entity_orm_to_dataclass(orm) for orm in orms]
