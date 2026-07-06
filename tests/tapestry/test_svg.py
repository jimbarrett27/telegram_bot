"""Unit tests for the pure SVG cleaning/stitching logic (no network/secrets)."""

import json
import re
import xml.dom.minidom as minidom

import pytest

from tapestry.svg import (
    OVERLAP,
    PANEL_HEIGHT,
    escape_bare_amps,
    extract_svg,
    stitch_svgs,
)

# A panel that (a) is NOT the canonical size, and (b) reuses id="bg" — the two
# things stitching has to cope with (rescaling + id collisions).
PANEL = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="100" '
    'viewBox="0 0 800 100">'
    '<defs><linearGradient id="bg"><stop offset="0%" stop-color="#123456"/></linearGradient></defs>'
    '<rect width="800" height="100" fill="url(#bg)"/>'
    '<a href="https://x.test/a?p=1&q=2"><circle cx="70" cy="50" r="4"/></a>'
    "</svg>"
)

BARE_AMP_RE = re.compile(r"&(?!#?\w+;)")

# Panels are always run through extract_svg (which escapes bare "&") before they
# reach stitch_svgs, so the stitch tests feed the cleaned form.
CLEAN_PANEL = escape_bare_amps(PANEL)


def test_escape_bare_amps_only_touches_bare_amps():
    assert escape_bare_amps("a & b") == "a &amp; b"
    # Existing valid entities must be left untouched.
    kept = "keep &amp; and &#38; and &#x26; and &nbsp;"
    assert escape_bare_amps(kept) == kept


def test_extract_svg_from_fenced_json():
    resp = "```json\n" + json.dumps({"plan": "p", "svg_string": PANEL}) + "\n```"
    svg = extract_svg(resp)
    assert svg.startswith("<svg")
    assert "p=1&amp;q=2" in svg  # bare & escaped
    assert not BARE_AMP_RE.search(svg)  # nothing left unescaped


def test_extract_svg_falls_back_to_raw_block():
    resp = "sure, here you go:\n" + PANEL + "\nhope that helps"
    assert extract_svg(resp).startswith("<svg")


def test_extract_svg_raises_without_svg():
    with pytest.raises(ValueError):
        extract_svg("there is no svg in this response")


def test_stitch_geometry_offsets_and_scale():
    out = stitch_svgs([CLEAN_PANEL, CLEAN_PANEL])
    minidom.parseString(out)  # must be well-formed XML

    step = PANEL_HEIGHT - OVERLAP
    total = step + PANEL_HEIGHT
    assert f'height="{total}"' in out
    assert "translate(0,0)" in out and f"translate(0,{step})" in out
    # 800x100 source scaled to the canonical 1600x200 -> scale(2,2), one per panel
    assert out.count("scale(2,2)") == 2


def test_stitch_namespaces_ids_to_avoid_collision():
    out = stitch_svgs([CLEAN_PANEL, CLEAN_PANEL])
    assert 'id="d0_bg"' in out and 'id="d1_bg"' in out
    assert 'id="bg"' not in out  # no bare, colliding id survives
    assert "url(#d0_bg)" in out and "url(#d1_bg)" in out


def test_stitch_empty_is_valid():
    out = stitch_svgs([])
    minidom.parseString(out)
    assert 'height="0"' in out
