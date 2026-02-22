"""Tests for PDF adventure parser."""

from pathlib import Path

import pytest

from dnd.pdf_parser import (
    parse_adventure_pdf,
    list_available_adventures,
    get_adventure_path,
    ADVENTURES_DIR,
)


class TestListAvailableAdventures:

    def test_finds_hangover(self):
        adventures = list_available_adventures()
        assert "Wiebe_TheHangover" in adventures

    def test_returns_sorted(self):
        adventures = list_available_adventures()
        assert adventures == sorted(adventures)


class TestGetAdventurePath:

    def test_exact_match(self):
        path = get_adventure_path("Wiebe_TheHangover")
        assert path is not None
        assert path.exists()
        assert path.suffix == ".pdf"

    def test_partial_match(self):
        path = get_adventure_path("hangover")
        assert path is not None
        assert "Hangover" in path.stem

    def test_not_found(self):
        path = get_adventure_path("NonexistentAdventure")
        assert path is None


HANGOVER_PDF = ADVENTURES_DIR / "Wiebe_TheHangover.pdf"


@pytest.mark.skipif(not HANGOVER_PDF.exists(), reason="Test PDF not available")
class TestParseAdventurePdf:

    def test_returns_sections(self):
        sections = parse_adventure_pdf(HANGOVER_PDF)
        assert len(sections) > 5

    def test_sections_have_titles(self):
        sections = parse_adventure_pdf(HANGOVER_PDF)
        for section in sections:
            assert "title" in section
            assert "content" in section
            assert len(section["title"]) > 0

    def test_sections_have_content(self):
        sections = parse_adventure_pdf(HANGOVER_PDF)
        for section in sections:
            assert len(section["content"]) > 0

    def test_finds_key_sections(self):
        sections = parse_adventure_pdf(HANGOVER_PDF)
        titles = [s["title"] for s in sections]
        # These are known section titles in the adventure
        assert any("Adventure Setup" in t for t in titles)
        assert any("Cast of Characters" in t for t in titles)
        assert any("Scene 1" in t for t in titles)
        assert any("Epilogue" in t for t in titles)

    def test_first_sections_serve_as_overview(self):
        sections = parse_adventure_pdf(HANGOVER_PDF)
        # First few sections should contain the adventure title/setup
        first_titles = [s["title"] for s in sections[:5]]
        assert any("HANGOVER" in t.upper() for t in first_titles)

    def test_split_heading_merged(self):
        """Scene 4's title spans two lines and should be merged."""
        sections = parse_adventure_pdf(HANGOVER_PDF)
        titles = [s["title"] for s in sections]
        assert any("Gold Statue of Impossible Gravity" in t for t in titles)
