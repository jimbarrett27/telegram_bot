"""
Zone-based spatial tracking tools for the DM agent.

Provides tools for managing scenes with zones, entity placement,
movement, and distance checking.
"""

import logging
from typing import Optional

from langchain_core.tools import tool

from dnd.database import (
    create_zone,
    get_zones,
    get_zone_by_name,
    clear_zones,
    add_zone_adjacency,
    get_adjacent_zones,
    get_zone_distance,
    place_entity_in_zone,
    remove_entity_from_zones,
    get_zone_occupants,
    get_entity_zone,
    get_all_zone_entities,
)

logger = logging.getLogger(__name__)


def _distance_description(hops: int) -> str:
    """Convert hop count to a human-readable distance description."""
    if hops == 0:
        return "Same zone (melee, ~5ft)"
    feet = hops * 15
    if hops == 1:
        return f"1 zone apart (~{feet}ft, close range)"
    if hops <= 2:
        return f"{hops} zones apart (~{feet}ft, close range)"
    if hops <= 4:
        return f"{hops} zones apart (~{feet}ft, medium range)"
    return f"{hops} zones apart (~{feet}ft, long range)"


class ZoneTools:
    """Tools for zone-based spatial tracking, bound to a specific game."""

    def __init__(self, game_id: int):
        self.game_id = game_id

    def as_tools(self):
        """Return LangChain tools bound to this game."""
        game_id = self.game_id

        @tool
        def setup_scene(
            zones: list[dict],
            connections: list[list[str]],
            entities: list[dict],
        ) -> str:
            """Set up a new scene with zones, connections, and entity placements in one call.

            Clears any existing zones first, then creates the full scene layout.
            Use this when the party enters a new location or an encounter begins.

            Args:
                zones: List of zone dicts, each with "name" and optionally "description".
                    Example: [{"name": "entrance", "description": "A wide stone doorway"},
                              {"name": "main hall", "description": "Pillared hall with a high ceiling"}]
                connections: List of zone name pairs that are adjacent.
                    Example: [["entrance", "main hall"], ["main hall", "back room"]]
                entities: List of entity dicts with "name", "zone", and optionally "type" (player/npc).
                    Example: [{"name": "Aragorn", "zone": "entrance", "type": "player"},
                              {"name": "Goblin #1", "zone": "main hall", "type": "npc"}]
            """
            logger.info("setup_scene called for game_id=%d: %d zones", game_id, len(zones))

            # Clear existing
            clear_zones(game_id)

            # Create zones
            created_zones = {}
            for z in zones:
                zone = create_zone(game_id, z["name"], z.get("description", ""))
                created_zones[z["name"].lower()] = zone

            # Create connections
            conn_count = 0
            for pair in connections:
                if len(pair) != 2:
                    continue
                za = created_zones.get(pair[0].lower())
                zb = created_zones.get(pair[1].lower())
                if za and zb:
                    add_zone_adjacency(za.id, zb.id)
                    conn_count += 1

            # Place entities
            entity_count = 0
            for ent in entities:
                zone = created_zones.get(ent["zone"].lower())
                if zone:
                    etype = ent.get("type", "npc")
                    place_entity_in_zone(zone.id, game_id, ent["name"], entity_type=etype)
                    entity_count += 1

            return (
                f"Scene created: {len(created_zones)} zones, "
                f"{conn_count} connections, {entity_count} entities placed."
            )

        @tool
        def place_entity(entity_name: str, zone_name: str, entity_type: str = "npc") -> str:
            """Place an entity in a zone. Moves the entity if already placed elsewhere.

            Use this to add new NPCs mid-scene or place latecomers.

            Args:
                entity_name: Name of the entity (e.g., "Goblin #3", "Aragorn")
                zone_name: Name of the zone to place them in
                entity_type: "player" or "npc" (default "npc")
            """
            logger.info("place_entity called: %r -> %r", entity_name, zone_name)
            zone = get_zone_by_name(game_id, zone_name)
            if zone is None:
                available = [z.name for z in get_zones(game_id)]
                return f"Zone '{zone_name}' not found. Available zones: {', '.join(available)}"

            place_entity_in_zone(zone.id, game_id, entity_name, entity_type=entity_type)
            return f"{entity_name} placed in '{zone.name}'."

        @tool
        def move_entity(entity_name: str, zone_name: str) -> str:
            """Move an entity to a different zone.

            Validates adjacency — if not adjacent, warns with hop count but still moves
            (DM may want to allow dashing or teleporting).

            Args:
                entity_name: Name of the entity to move
                zone_name: Name of the destination zone
            """
            logger.info("move_entity called: %r -> %r", entity_name, zone_name)
            dest_zone = get_zone_by_name(game_id, zone_name)
            if dest_zone is None:
                available = [z.name for z in get_zones(game_id)]
                return f"Zone '{zone_name}' not found. Available zones: {', '.join(available)}"

            current_zone = get_entity_zone(game_id, entity_name)
            if current_zone is None:
                # Not placed yet — just place them
                place_entity_in_zone(dest_zone.id, game_id, entity_name)
                return f"{entity_name} placed in '{dest_zone.name}' (was not previously placed)."

            if current_zone.id == dest_zone.id:
                return f"{entity_name} is already in '{dest_zone.name}'."

            # Check adjacency
            adjacent = get_adjacent_zones(current_zone.id)
            adjacent_ids = {z.id for z in adjacent}
            warning = ""
            if dest_zone.id not in adjacent_ids:
                dist = get_zone_distance(game_id, current_zone.name, dest_zone.name)
                if dist is not None:
                    warning = (
                        f" Warning: not adjacent — {dist} zones apart "
                        f"(~{dist * 15}ft). Moved anyway (dash/teleport)."
                    )
                else:
                    warning = " Warning: zones are not connected. Moved anyway (teleport)."

            place_entity_in_zone(dest_zone.id, game_id, entity_name)
            return f"{entity_name} moved from '{current_zone.name}' to '{dest_zone.name}'.{warning}"

        @tool
        def remove_entity(entity_name: str) -> str:
            """Remove an entity from all zones (dead, fled, disappeared).

            Args:
                entity_name: Name of the entity to remove
            """
            logger.info("remove_entity called: %r", entity_name)
            current = get_entity_zone(game_id, entity_name)
            if current is None:
                return f"{entity_name} is not in any zone."

            remove_entity_from_zones(game_id, entity_name)
            return f"{entity_name} removed from zones (was in '{current.name}')."

        @tool
        def get_zone_map() -> str:
            """Get the full zone map showing all zones, connections, and occupants.

            Returns a formatted text map of the current scene layout.
            """
            logger.info("get_zone_map called for game_id=%d", game_id)
            zones = get_zones(game_id)
            if not zones:
                return "No zones set up. Use setup_scene to create a scene."

            lines = ["=== Zone Map ===", ""]

            # Zones and occupants
            lines.append("Zones:")
            for z in zones:
                desc = f" — {z.description}" if z.description else ""
                occupants = get_zone_occupants(z.id)
                occ_str = ""
                if occupants:
                    names = [f"{e.name} ({e.entity_type})" for e in occupants]
                    occ_str = f" [{', '.join(names)}]"
                lines.append(f"  • {z.name}{desc}{occ_str}")

            # Connections
            lines.append("")
            lines.append("Connections:")
            seen = set()
            for z in zones:
                adjacent = get_adjacent_zones(z.id)
                for adj in adjacent:
                    pair = tuple(sorted([z.name, adj.name]))
                    if pair not in seen:
                        seen.add(pair)
                        lines.append(f"  {pair[0]} <-> {pair[1]}")

            if not seen:
                lines.append("  (no connections)")

            return "\n".join(lines)

        @tool
        def check_distance(entity_a: str, entity_b: str) -> str:
            """Check the distance between two entities in zones.

            Returns the hop count and approximate distance in feet.

            Args:
                entity_a: Name of the first entity
                entity_b: Name of the second entity
            """
            logger.info("check_distance called: %r <-> %r", entity_a, entity_b)
            zone_a = get_entity_zone(game_id, entity_a)
            zone_b = get_entity_zone(game_id, entity_b)

            if zone_a is None:
                return f"{entity_a} is not in any zone."
            if zone_b is None:
                return f"{entity_b} is not in any zone."

            if zone_a.id == zone_b.id:
                return f"{entity_a} and {entity_b} are in the same zone ('{zone_a.name}'). {_distance_description(0)}"

            dist = get_zone_distance(game_id, zone_a.name, zone_b.name)
            if dist is None:
                return (
                    f"{entity_a} (in '{zone_a.name}') and {entity_b} (in '{zone_b.name}') "
                    f"are in disconnected zones — no path between them."
                )

            return (
                f"{entity_a} (in '{zone_a.name}') and {entity_b} (in '{zone_b.name}'): "
                f"{_distance_description(dist)}"
            )

        @tool
        def clear_scene() -> str:
            """Clear all zones, connections, and entity placements for a scene transition.

            Use this when the party moves to a completely new location.
            Note: setup_scene already calls this automatically.
            """
            logger.info("clear_scene called for game_id=%d", game_id)
            clear_zones(game_id)
            return "All zones cleared. Ready for new scene setup."

        return [setup_scene, place_entity, move_entity, remove_entity, get_zone_map, check_distance, clear_scene]
