"""Tests for zone-based spatial tracking: database operations and tools."""

import pytest
from sqlalchemy import create_engine

from dnd import db_engine
from dnd.models import CharacterClass
from dnd.orm_models import Base


@pytest.fixture
def temp_db():
    """Create a temporary in-memory database for testing."""
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)
    db_engine.set_engine(test_engine)
    yield test_engine
    db_engine.reset_engine()


@pytest.fixture
def game(temp_db):
    """Create a game for testing."""
    from dnd.database import create_game
    return create_game(chat_id=12345)


@pytest.fixture
def game_with_player(game):
    """Create a game with one player."""
    from dnd.database import add_player
    player = add_player(
        game_id=game.id,
        telegram_user_id=100,
        telegram_username="alice",
        character_name="Aragorn",
        character_class=CharacterClass.WARRIOR,
    )
    return game, player


# === Database Tests ===


class TestZoneCRUD:

    def test_create_zone(self, game):
        from dnd.database import create_zone
        zone = create_zone(game.id, "entrance", "A wide stone doorway")
        assert zone.id is not None
        assert zone.game_id == game.id
        assert zone.name == "entrance"
        assert zone.description == "A wide stone doorway"
        assert zone.created_at > 0

    def test_get_zones(self, game):
        from dnd.database import create_zone, get_zones
        create_zone(game.id, "entrance")
        create_zone(game.id, "main hall")
        zones = get_zones(game.id)
        assert len(zones) == 2
        assert zones[0].name == "entrance"
        assert zones[1].name == "main hall"

    def test_get_zones_empty(self, game):
        from dnd.database import get_zones
        assert get_zones(game.id) == []

    def test_get_zone_by_name(self, game):
        from dnd.database import create_zone, get_zone_by_name
        create_zone(game.id, "Entrance Hall")
        zone = get_zone_by_name(game.id, "entrance hall")
        assert zone is not None
        assert zone.name == "Entrance Hall"

    def test_get_zone_by_name_not_found(self, game):
        from dnd.database import get_zone_by_name
        assert get_zone_by_name(game.id, "nonexistent") is None

    def test_delete_zone_cascades(self, game):
        from dnd.database import (
            create_zone, delete_zone, get_zones,
            add_zone_adjacency, get_adjacent_zones,
            place_entity_in_zone, get_zone_occupants,
        )
        z1 = create_zone(game.id, "zone1")
        z2 = create_zone(game.id, "zone2")
        add_zone_adjacency(z1.id, z2.id)
        place_entity_in_zone(z1.id, game.id, "Goblin")

        delete_zone(z1.id)

        assert len(get_zones(game.id)) == 1
        assert get_adjacent_zones(z2.id) == []
        assert get_zone_occupants(z1.id) == []

    def test_clear_zones(self, game):
        from dnd.database import (
            create_zone, clear_zones, get_zones,
            add_zone_adjacency, place_entity_in_zone,
            get_all_zone_entities,
        )
        z1 = create_zone(game.id, "zone1")
        z2 = create_zone(game.id, "zone2")
        add_zone_adjacency(z1.id, z2.id)
        place_entity_in_zone(z1.id, game.id, "Goblin")

        clear_zones(game.id)

        assert get_zones(game.id) == []
        assert get_all_zone_entities(game.id) == []

    def test_clear_zones_leaves_other_games(self, temp_db):
        from dnd.database import create_game, create_zone, clear_zones, get_zones
        game1 = create_game(chat_id=11111)
        game2 = create_game(chat_id=22222)
        create_zone(game1.id, "zone_a")
        create_zone(game2.id, "zone_b")

        clear_zones(game1.id)

        assert get_zones(game1.id) == []
        assert len(get_zones(game2.id)) == 1


class TestZoneAdjacency:

    def test_add_adjacency(self, game):
        from dnd.database import create_zone, add_zone_adjacency
        z1 = create_zone(game.id, "zone1")
        z2 = create_zone(game.id, "zone2")
        adj = add_zone_adjacency(z1.id, z2.id)
        assert adj.id is not None
        assert adj.zone_a_id == min(z1.id, z2.id)
        assert adj.zone_b_id == max(z1.id, z2.id)

    def test_smaller_id_first(self, game):
        from dnd.database import create_zone, add_zone_adjacency
        z1 = create_zone(game.id, "zone1")
        z2 = create_zone(game.id, "zone2")
        # Pass larger ID first
        adj = add_zone_adjacency(z2.id, z1.id)
        assert adj.zone_a_id == z1.id
        assert adj.zone_b_id == z2.id

    def test_get_adjacent_bidirectional(self, game):
        from dnd.database import create_zone, add_zone_adjacency, get_adjacent_zones
        z1 = create_zone(game.id, "zone1")
        z2 = create_zone(game.id, "zone2")
        add_zone_adjacency(z1.id, z2.id)

        adj_from_1 = get_adjacent_zones(z1.id)
        adj_from_2 = get_adjacent_zones(z2.id)
        assert len(adj_from_1) == 1
        assert adj_from_1[0].id == z2.id
        assert len(adj_from_2) == 1
        assert adj_from_2[0].id == z1.id


class TestEntityPlacement:

    def test_place_entity(self, game):
        from dnd.database import create_zone, place_entity_in_zone
        z = create_zone(game.id, "entrance")
        entity = place_entity_in_zone(z.id, game.id, "Goblin #1", entity_type="npc")
        assert entity.id is not None
        assert entity.name == "Goblin #1"
        assert entity.entity_type == "npc"
        assert entity.zone_id == z.id

    def test_place_player(self, game_with_player):
        game, player = game_with_player
        from dnd.database import create_zone, place_entity_in_zone
        z = create_zone(game.id, "entrance")
        entity = place_entity_in_zone(z.id, game.id, "Aragorn", player_id=player.id, entity_type="player")
        assert entity.player_id == player.id
        assert entity.entity_type == "player"

    def test_move_entity_replaces(self, game):
        from dnd.database import create_zone, place_entity_in_zone, get_entity_zone
        z1 = create_zone(game.id, "zone1")
        z2 = create_zone(game.id, "zone2")
        place_entity_in_zone(z1.id, game.id, "Goblin")
        place_entity_in_zone(z2.id, game.id, "Goblin")

        zone = get_entity_zone(game.id, "Goblin")
        assert zone.id == z2.id

    def test_remove_entity(self, game):
        from dnd.database import create_zone, place_entity_in_zone, remove_entity_from_zones, get_entity_zone
        z = create_zone(game.id, "entrance")
        place_entity_in_zone(z.id, game.id, "Goblin")
        remove_entity_from_zones(game.id, "Goblin")
        assert get_entity_zone(game.id, "Goblin") is None

    def test_get_zone_occupants(self, game):
        from dnd.database import create_zone, place_entity_in_zone, get_zone_occupants
        z = create_zone(game.id, "entrance")
        place_entity_in_zone(z.id, game.id, "Goblin #1")
        place_entity_in_zone(z.id, game.id, "Goblin #2")
        occupants = get_zone_occupants(z.id)
        assert len(occupants) == 2
        names = {e.name for e in occupants}
        assert names == {"Goblin #1", "Goblin #2"}

    def test_get_entity_zone(self, game):
        from dnd.database import create_zone, place_entity_in_zone, get_entity_zone
        z = create_zone(game.id, "entrance")
        place_entity_in_zone(z.id, game.id, "Goblin")
        zone = get_entity_zone(game.id, "Goblin")
        assert zone is not None
        assert zone.name == "entrance"

    def test_get_entity_zone_not_placed(self, game):
        from dnd.database import get_entity_zone
        assert get_entity_zone(game.id, "Nobody") is None


class TestZoneDistance:

    def test_same_zone(self, game):
        from dnd.database import create_zone, get_zone_distance
        create_zone(game.id, "entrance")
        assert get_zone_distance(game.id, "entrance", "entrance") == 0

    def test_adjacent(self, game):
        from dnd.database import create_zone, add_zone_adjacency, get_zone_distance
        z1 = create_zone(game.id, "zone1")
        z2 = create_zone(game.id, "zone2")
        add_zone_adjacency(z1.id, z2.id)
        assert get_zone_distance(game.id, "zone1", "zone2") == 1

    def test_two_hops(self, game):
        from dnd.database import create_zone, add_zone_adjacency, get_zone_distance
        z1 = create_zone(game.id, "zone1")
        z2 = create_zone(game.id, "zone2")
        z3 = create_zone(game.id, "zone3")
        add_zone_adjacency(z1.id, z2.id)
        add_zone_adjacency(z2.id, z3.id)
        assert get_zone_distance(game.id, "zone1", "zone3") == 2

    def test_unreachable(self, game):
        from dnd.database import create_zone, get_zone_distance
        create_zone(game.id, "zone1")
        create_zone(game.id, "zone2")
        assert get_zone_distance(game.id, "zone1", "zone2") is None

    def test_nonexistent_zone(self, game):
        from dnd.database import get_zone_distance
        assert get_zone_distance(game.id, "zone1", "zone2") is None


class TestDeleteGameCleansZones:

    def test_delete_game_cleans_zones(self, temp_db):
        from dnd.database import create_game, create_zone, place_entity_in_zone, delete_game, get_zones
        game = create_game(chat_id=12345)
        z = create_zone(game.id, "entrance")
        place_entity_in_zone(z.id, game.id, "Goblin")
        delete_game(12345)
        assert get_zones(game.id) == []


# === Tool Tests ===


class TestSetupScene:

    def test_setup_scene_creates_all(self, game):
        from dnd.zone_tools import ZoneTools
        from dnd.database import get_zones, get_all_zone_entities
        tools = ZoneTools(game.id).as_tools()
        setup = tools[0]

        result = setup.invoke({
            "zones": [
                {"name": "entrance", "description": "Front door"},
                {"name": "main hall", "description": "Big room"},
                {"name": "back room"},
            ],
            "connections": [["entrance", "main hall"], ["main hall", "back room"]],
            "entities": [
                {"name": "Aragorn", "zone": "entrance", "type": "player"},
                {"name": "Goblin #1", "zone": "main hall", "type": "npc"},
            ],
        })

        assert "3 zones" in result
        assert "2 connections" in result
        assert "2 entities" in result
        assert len(get_zones(game.id)) == 3
        assert len(get_all_zone_entities(game.id)) == 2

    def test_setup_scene_clears_existing(self, game):
        from dnd.zone_tools import ZoneTools
        from dnd.database import get_zones, create_zone
        create_zone(game.id, "old_zone")

        tools = ZoneTools(game.id).as_tools()
        setup = tools[0]
        setup.invoke({
            "zones": [{"name": "new_zone"}],
            "connections": [],
            "entities": [],
        })

        zones = get_zones(game.id)
        assert len(zones) == 1
        assert zones[0].name == "new_zone"


class TestPlaceEntity:

    def test_place_entity_tool(self, game):
        from dnd.zone_tools import ZoneTools
        from dnd.database import create_zone, get_entity_zone
        create_zone(game.id, "entrance")
        tools = ZoneTools(game.id).as_tools()
        place = tools[1]

        result = place.invoke({"entity_name": "Goblin", "zone_name": "entrance"})
        assert "placed" in result
        assert get_entity_zone(game.id, "Goblin").name == "entrance"

    def test_place_entity_unknown_zone(self, game):
        from dnd.zone_tools import ZoneTools
        tools = ZoneTools(game.id).as_tools()
        place = tools[1]
        result = place.invoke({"entity_name": "Goblin", "zone_name": "nowhere"})
        assert "not found" in result


class TestMoveEntity:

    def test_move_adjacent(self, game):
        from dnd.zone_tools import ZoneTools
        from dnd.database import create_zone, add_zone_adjacency, place_entity_in_zone, get_entity_zone
        z1 = create_zone(game.id, "zone1")
        z2 = create_zone(game.id, "zone2")
        add_zone_adjacency(z1.id, z2.id)
        place_entity_in_zone(z1.id, game.id, "Aragorn")

        tools = ZoneTools(game.id).as_tools()
        move = tools[2]
        result = move.invoke({"entity_name": "Aragorn", "zone_name": "zone2"})
        assert "moved" in result.lower()
        assert "Warning" not in result
        assert get_entity_zone(game.id, "Aragorn").name == "zone2"

    def test_move_non_adjacent_warns(self, game):
        from dnd.zone_tools import ZoneTools
        from dnd.database import create_zone, add_zone_adjacency, place_entity_in_zone, get_entity_zone
        z1 = create_zone(game.id, "zone1")
        z2 = create_zone(game.id, "zone2")
        z3 = create_zone(game.id, "zone3")
        add_zone_adjacency(z1.id, z2.id)
        add_zone_adjacency(z2.id, z3.id)
        place_entity_in_zone(z1.id, game.id, "Aragorn")

        tools = ZoneTools(game.id).as_tools()
        move = tools[2]
        result = move.invoke({"entity_name": "Aragorn", "zone_name": "zone3"})
        assert "Warning" in result
        assert "2 zones apart" in result
        assert get_entity_zone(game.id, "Aragorn").name == "zone3"


class TestRemoveEntity:

    def test_remove_entity_tool(self, game):
        from dnd.zone_tools import ZoneTools
        from dnd.database import create_zone, place_entity_in_zone, get_entity_zone
        z = create_zone(game.id, "entrance")
        place_entity_in_zone(z.id, game.id, "Goblin")

        tools = ZoneTools(game.id).as_tools()
        remove = tools[3]
        result = remove.invoke({"entity_name": "Goblin"})
        assert "removed" in result.lower()
        assert get_entity_zone(game.id, "Goblin") is None

    def test_remove_entity_not_found(self, game):
        from dnd.zone_tools import ZoneTools
        tools = ZoneTools(game.id).as_tools()
        remove = tools[3]
        result = remove.invoke({"entity_name": "Nobody"})
        assert "not in any zone" in result


class TestGetZoneMap:

    def test_zone_map_format(self, game):
        from dnd.zone_tools import ZoneTools
        from dnd.database import create_zone, add_zone_adjacency, place_entity_in_zone
        z1 = create_zone(game.id, "entrance", "A doorway")
        z2 = create_zone(game.id, "main hall")
        add_zone_adjacency(z1.id, z2.id)
        place_entity_in_zone(z1.id, game.id, "Aragorn", entity_type="player")

        tools = ZoneTools(game.id).as_tools()
        get_map = tools[4]
        result = get_map.invoke({})
        assert "entrance" in result
        assert "main hall" in result
        assert "Aragorn" in result
        assert "<->" in result

    def test_zone_map_empty(self, game):
        from dnd.zone_tools import ZoneTools
        tools = ZoneTools(game.id).as_tools()
        get_map = tools[4]
        result = get_map.invoke({})
        assert "No zones" in result


class TestCheckDistance:

    def test_same_zone(self, game):
        from dnd.zone_tools import ZoneTools
        from dnd.database import create_zone, place_entity_in_zone
        z = create_zone(game.id, "entrance")
        place_entity_in_zone(z.id, game.id, "Aragorn")
        place_entity_in_zone(z.id, game.id, "Goblin")

        tools = ZoneTools(game.id).as_tools()
        check = tools[5]
        result = check.invoke({"entity_a": "Aragorn", "entity_b": "Goblin"})
        assert "same zone" in result.lower()
        assert "melee" in result.lower()

    def test_distant_entities(self, game):
        from dnd.zone_tools import ZoneTools
        from dnd.database import create_zone, add_zone_adjacency, place_entity_in_zone
        z1 = create_zone(game.id, "zone1")
        z2 = create_zone(game.id, "zone2")
        z3 = create_zone(game.id, "zone3")
        add_zone_adjacency(z1.id, z2.id)
        add_zone_adjacency(z2.id, z3.id)
        place_entity_in_zone(z1.id, game.id, "Aragorn")
        place_entity_in_zone(z3.id, game.id, "Goblin")

        tools = ZoneTools(game.id).as_tools()
        check = tools[5]
        result = check.invoke({"entity_a": "Aragorn", "entity_b": "Goblin"})
        assert "2 zones apart" in result
        assert "30ft" in result

    def test_unknown_entity(self, game):
        from dnd.zone_tools import ZoneTools
        from dnd.database import create_zone, place_entity_in_zone
        z = create_zone(game.id, "entrance")
        place_entity_in_zone(z.id, game.id, "Aragorn")

        tools = ZoneTools(game.id).as_tools()
        check = tools[5]
        result = check.invoke({"entity_a": "Aragorn", "entity_b": "Ghost"})
        assert "not in any zone" in result


class TestClearScene:

    def test_clear_scene_tool(self, game):
        from dnd.zone_tools import ZoneTools
        from dnd.database import create_zone, get_zones
        create_zone(game.id, "entrance")

        tools = ZoneTools(game.id).as_tools()
        clear = tools[6]
        result = clear.invoke({})
        assert "cleared" in result.lower()
        assert get_zones(game.id) == []
