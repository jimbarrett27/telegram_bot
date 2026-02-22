"""Tests for campaign section database operations and tools."""

import pytest
from sqlalchemy import create_engine

from dnd import db_engine
from dnd.orm_models import Base
from dnd.database import (
    create_game,
    store_campaign_sections,
    get_campaign_sections,
    search_campaign_sections,
    delete_game,
)
from dnd.campaign_tools import CampaignTools


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
    """Create a game."""
    return create_game(chat_id=12345)


SAMPLE_SECTIONS = [
    {"title": "THE HANGOVER", "content": "A Rat Queens adventure for 3rd-level characters."},
    {"title": "Adventure Setup", "content": "This adventure follows the aftermath of an insane night."},
    {"title": "Cast of Characters", "content": "Sir Dandeleone is a rich noble. Larry Halfmandini is a smidgen circus performer."},
    {"title": "Scene 1: Ogre a' Sniffin'", "content": "An ogre appears on the road, sniffing for food."},
    {"title": "Scene 2: Bandits on the Road!", "content": "Drake and his bandits ambush the party."},
]


class TestStoreCampaignSections:

    def test_store_and_retrieve(self, game):
        store_campaign_sections(game.id, SAMPLE_SECTIONS)
        sections = get_campaign_sections(game.id)
        assert len(sections) == 5
        assert sections[0].section_title == "THE HANGOVER"
        assert sections[4].section_title == "Scene 2: Bandits on the Road!"

    def test_section_order_preserved(self, game):
        store_campaign_sections(game.id, SAMPLE_SECTIONS)
        sections = get_campaign_sections(game.id)
        for i, section in enumerate(sections):
            assert section.section_order == i

    def test_empty_sections(self, game):
        store_campaign_sections(game.id, [])
        sections = get_campaign_sections(game.id)
        assert sections == []

    def test_no_sections_for_other_game(self, game, temp_db):
        store_campaign_sections(game.id, SAMPLE_SECTIONS)
        other_game = create_game(chat_id=99999)
        sections = get_campaign_sections(other_game.id)
        assert sections == []


class TestSearchCampaignSections:

    def test_search_by_title(self, game):
        store_campaign_sections(game.id, SAMPLE_SECTIONS)
        results = search_campaign_sections(game.id, "Ogre")
        assert len(results) == 1
        assert "Ogre" in results[0].section_title

    def test_search_by_content(self, game):
        store_campaign_sections(game.id, SAMPLE_SECTIONS)
        results = search_campaign_sections(game.id, "noble")
        assert len(results) == 1
        assert "Cast of Characters" in results[0].section_title

    def test_search_case_insensitive(self, game):
        store_campaign_sections(game.id, SAMPLE_SECTIONS)
        results = search_campaign_sections(game.id, "ogre")
        assert len(results) == 1

    def test_search_no_results(self, game):
        store_campaign_sections(game.id, SAMPLE_SECTIONS)
        results = search_campaign_sections(game.id, "dragon")
        assert results == []

    def test_search_multiple_matches(self, game):
        store_campaign_sections(game.id, SAMPLE_SECTIONS)
        results = search_campaign_sections(game.id, "Scene")
        assert len(results) == 2


class TestDeleteGameCleansUpSections:

    def test_sections_deleted_with_game(self, game):
        store_campaign_sections(game.id, SAMPLE_SECTIONS)
        assert len(get_campaign_sections(game.id)) == 5

        delete_game(game.chat_id)
        assert get_campaign_sections(game.id) == []


class TestCampaignToolsFunctions:

    def test_lookup_campaign_returns_matches(self, game):
        store_campaign_sections(game.id, SAMPLE_SECTIONS)
        tools = CampaignTools(game.id).as_tools()
        lookup = tools[0]  # lookup_campaign

        result = lookup.invoke({"query": "Ogre"})
        assert "Ogre" in result
        assert "sniffing" in result

    def test_lookup_campaign_no_match(self, game):
        store_campaign_sections(game.id, SAMPLE_SECTIONS)
        tools = CampaignTools(game.id).as_tools()
        lookup = tools[0]

        result = lookup.invoke({"query": "dragon"})
        assert "No adventure content found" in result

    def test_list_sections(self, game):
        store_campaign_sections(game.id, SAMPLE_SECTIONS)
        tools = CampaignTools(game.id).as_tools()
        list_sections = tools[1]  # list_campaign_sections

        result = list_sections.invoke({})
        assert "THE HANGOVER" in result
        assert "Adventure Setup" in result
        assert "Scene 1" in result

    def test_list_sections_empty(self, game):
        tools = CampaignTools(game.id).as_tools()
        list_sections = tools[1]

        result = list_sections.invoke({})
        assert "No adventure sections" in result
