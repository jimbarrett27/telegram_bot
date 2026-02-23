"""Tests for the deterministic markdown campaign loader."""

from pathlib import Path
from unittest.mock import patch

import pytest

from dnd.campaign_loader import (
    parse_campaign_markdown,
    list_available_campaigns,
    get_campaign_path,
    load_campaign,
    CAMPAIGNS_DIR,
)


@pytest.fixture
def sample_md(tmp_path):
    """Create a sample campaign markdown file."""
    content = """\
# Test Adventure

A brief introduction to the adventure.

## Adventure Setup

The party arrives at the dungeon entrance.

## Cast of Characters

- **Bob** — A friendly NPC.
- **Evil Guy** — The villain.

## Scene 1: The Entrance

A dark corridor stretches ahead.

## Scene 2: The Boss Room

The villain awaits.
"""
    md_file = tmp_path / "test_adventure.md"
    md_file.write_text(content)
    return md_file


class TestParseCampaignMarkdown:

    def test_basic_sections(self, sample_md):
        sections = parse_campaign_markdown(sample_md)
        titles = [s["title"] for s in sections]
        assert "Introduction" in titles
        assert "Adventure Setup" in titles
        assert "Cast of Characters" in titles
        assert "Scene 1: The Entrance" in titles
        assert "Scene 2: The Boss Room" in titles

    def test_introduction_before_first_heading(self, sample_md):
        sections = parse_campaign_markdown(sample_md)
        intro = sections[0]
        assert intro["title"] == "Introduction"
        assert "# Test Adventure" in intro["content"]
        assert "brief introduction" in intro["content"]

    def test_empty_sections_filtered(self, tmp_path):
        content = "## Heading One\n\nSome content.\n\n## Empty Section\n\n## Heading Two\n\nMore content."
        md_file = tmp_path / "test.md"
        md_file.write_text(content)

        sections = parse_campaign_markdown(md_file)
        titles = [s["title"] for s in sections]
        assert "Empty Section" not in titles
        assert "Heading One" in titles
        assert "Heading Two" in titles

    def test_content_formatting_preserved(self, sample_md):
        sections = parse_campaign_markdown(sample_md)
        cast = next(s for s in sections if s["title"] == "Cast of Characters")
        assert "**Bob**" in cast["content"]
        assert "- " in cast["content"]

    def test_section_count(self, sample_md):
        sections = parse_campaign_markdown(sample_md)
        assert len(sections) == 5


class TestListAvailableCampaigns:

    def test_finds_goblin_caves(self):
        campaigns = list_available_campaigns()
        assert "goblin_caves" in campaigns

    def test_returns_sorted(self):
        campaigns = list_available_campaigns()
        assert campaigns == sorted(campaigns)

    def test_empty_dir(self, tmp_path):
        with patch("dnd.campaign_loader.CAMPAIGNS_DIR", tmp_path):
            campaigns = list_available_campaigns()
            assert campaigns == []


class TestGetCampaignPath:

    def test_exact_match(self):
        path = get_campaign_path("goblin_caves")
        assert path is not None
        assert path.exists()
        assert path.suffix == ".md"

    def test_partial_match(self):
        path = get_campaign_path("goblin")
        assert path is not None
        assert "goblin_caves" in path.stem

    def test_case_insensitive(self):
        path = get_campaign_path("GOBLIN")
        assert path is not None

    def test_not_found(self):
        path = get_campaign_path("nonexistent_campaign_xyz")
        assert path is None


class TestLoadCampaign:

    def test_stores_sections_and_returns_summary(self):
        with patch("dnd.campaign_loader.store_campaign_sections") as mock_store:
            summary = load_campaign(999, "goblin_caves")

            # Verify sections were stored
            mock_store.assert_called_once()
            call_args = mock_store.call_args
            assert call_args[0][0] == 999  # game_id
            sections = call_args[0][1]
            assert len(sections) > 0
            assert all("title" in s and "content" in s for s in sections)

            # Verify summary content
            assert "goblin_caves" in summary
            assert "lookup_campaign" in summary

    def test_summary_uses_first_4_sections(self):
        with patch("dnd.campaign_loader.store_campaign_sections"):
            summary = load_campaign(999, "goblin_caves")
            # Should contain content from early sections
            assert "Introduction" in summary or "Adventure Setup" in summary

    def test_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError) as exc_info:
            load_campaign(999, "nonexistent_campaign_xyz")
        assert "not found" in str(exc_info.value)
        assert "Available:" in str(exc_info.value)

    def test_error_lists_available(self):
        with pytest.raises(FileNotFoundError) as exc_info:
            load_campaign(999, "nonexistent_campaign_xyz")
        assert "goblin_caves" in str(exc_info.value)
