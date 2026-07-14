"""SVG helpers for the news tapestry: cleaning model output and stitching panels.

Deliberately stdlib-only and free of any network/secret access, so the geometry
can be unit-tested without authenticating to anything. The OpenRouter call lives
in :mod:`tapestry.generator`.
"""

import json
import re
import xml.etree.ElementTree as ET

# --- Panel geometry -------------------------------------------------------
# Every daily panel is drawn at this size. Panels overlap by OVERLAP pixels:
# the top OVERLAP px of a panel sits on top of the bottom OVERLAP px of the
# previous day's panel, so each new day adds (PANEL_HEIGHT - OVERLAP) px.
PANEL_WIDTH = 1600
PANEL_HEIGHT = 200
OVERLAP = 40


# --- Extracting the SVG from a model response -----------------------------

_SVG_OPEN_RE = re.compile(r"<svg\b[^>]*>", re.IGNORECASE)
_SVG_CLOSE_RE = re.compile(r"</svg\s*>", re.IGNORECASE)
_SVG_BLOCK_RE = re.compile(r"<svg\b.*</svg\s*>", re.IGNORECASE | re.DOTALL)
_FENCE_START_RE = re.compile(r"^```(?:json|svg|xml)?\s*", re.IGNORECASE)
_FENCE_END_RE = re.compile(r"\s*```$")


def escape_bare_amps(svg: str) -> str:
    """Escape ``&`` that isn't already part of a valid XML entity.

    Model-generated SVGs routinely embed raw ``&`` in URLs, which breaks XML
    parsing/rendering.
    """
    return re.sub(r"&(?!#?\w+;)", "&amp;", svg)


def clean_svg(svg: str) -> str:
    """Tidy a raw SVG string so it parses/renders cleanly."""
    return escape_bare_amps(svg.strip())


def extract_panel(content: str) -> tuple[str, str | None]:
    """Pull the cleaned SVG *and* the model's plan out of its message content.

    The model is asked for JSON with ``svg_string`` and ``plan`` keys. This
    tolerates stray markdown fences, and falls back to grabbing a raw
    ``<svg>...</svg>`` block (with no plan) if the JSON can't be parsed.

    Returns ``(svg, plan)``; ``plan`` is ``None`` when it wasn't provided (e.g.
    the raw-block fallback).
    """
    text = content.strip()
    text = _FENCE_START_RE.sub("", text)
    text = _FENCE_END_RE.sub("", text)

    plan = None
    try:
        parsed = json.loads(text)
        svg = parsed["svg_string"]
        plan = parsed.get("plan")
    except (json.JSONDecodeError, KeyError, TypeError):
        match = _SVG_BLOCK_RE.search(text)
        if not match:
            raise ValueError("No SVG found in model response")
        svg = match.group(0)

    return clean_svg(svg), plan


def extract_svg(content: str) -> str:
    """Pull just the cleaned SVG string out of the model's message content.

    Thin wrapper over :func:`extract_panel` for callers that don't need the plan.
    """
    return extract_panel(content)[0]


# --- Structural validation ------------------------------------------------
# The website renders these panels in a browser (very lenient), so we don't
# rasterise here -- that would need a native renderer whose coverage differs
# from the browser's and would add a new way for the daily job to fail. Instead
# we do dependency-free structural checks that catch the failure modes actually
# seen from LLMs: truncated/junk output (not well-formed XML), panels that are
# nearly empty (truncated early), and references to ids that were never defined
# (a blank gradient/filter). ``svg_problems`` returns a human-readable list so
# the retry log can say *why* a panel was rejected.

# Elements that actually put ink on the canvas. A valid panel should have a
# healthy number of these; the prompt asks for >= 50, so requiring a handful is
# very safe and only rejects badly truncated output.
_DRAWABLE_TAGS = frozenset({
    "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
    "text", "image", "use",
})
_MIN_DRAWABLE_ELEMENTS = 8

_URL_REF_RE = re.compile(r"url\(\s*#([^)\s]+)\s*\)")
_HREF_REF_RE = re.compile(r'(?:xlink:)?href\s*=\s*"#([^"]+)"')


def _local_name(tag: str) -> str:
    """Strip any ``{namespace}`` prefix ElementTree adds to a tag name."""
    return tag.rsplit("}", 1)[-1].lower()


def svg_problems(svg: str) -> list[str]:
    """Return a list of structural problems with ``svg`` (empty list == valid).

    Checks, in order: it parses as XML, its root is an ``<svg>`` element, it has
    enough drawable elements to be a real panel, and every ``url(#id)`` /
    ``href="#id"`` reference points to an id defined in the document.
    """
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        return [f"not well-formed XML: {exc}"]

    if _local_name(root.tag) != "svg":
        return [f"root element is <{_local_name(root.tag)}>, not <svg>"]

    problems: list[str] = []

    elements = list(root.iter())
    drawable = sum(1 for el in elements if _local_name(el.tag) in _DRAWABLE_TAGS)
    if drawable < _MIN_DRAWABLE_ELEMENTS:
        problems.append(
            f"only {drawable} drawable element(s) (need >= {_MIN_DRAWABLE_ELEMENTS}); "
            "likely truncated or near-empty"
        )

    defined_ids = {
        el.get("id") for el in elements if el.get("id") is not None
    }
    referenced = set(_URL_REF_RE.findall(svg)) | set(_HREF_REF_RE.findall(svg))
    dangling = sorted(referenced - defined_ids)
    if dangling:
        problems.append(
            "references undefined id(s): " + ", ".join(dangling)
        )

    return problems


def is_valid_svg(svg: str) -> bool:
    """True if ``svg`` has no structural problems (see :func:`svg_problems`)."""
    return not svg_problems(svg)


# --- Stitching panels into one tapestry -----------------------------------


def _svg_inner(svg: str) -> str:
    """Return the markup between the outer ``<svg>`` and ``</svg>`` tags."""
    open_match = _SVG_OPEN_RE.search(svg)
    close_match = None
    for close_match in _SVG_CLOSE_RE.finditer(svg):
        pass  # keep the last closing tag
    if open_match is None or close_match is None:
        raise ValueError("String does not contain a well-formed <svg> element")
    return svg[open_match.end():close_match.start()].strip()


def _svg_dimensions(svg: str, default_w: float, default_h: float):
    """Best-effort read of a panel's intrinsic width/height.

    Prefers the viewBox (its width/height), then explicit width/height
    attributes, then the supplied defaults.
    """
    open_tag = _SVG_OPEN_RE.search(svg).group(0)

    viewbox = re.search(r'viewBox\s*=\s*"([-\d.\s]+)"', open_tag)
    if viewbox:
        parts = viewbox.group(1).split()
        if len(parts) == 4:
            return float(parts[2]), float(parts[3])

    width = re.search(r'\bwidth\s*=\s*"([\d.]+)', open_tag)
    height = re.search(r'\bheight\s*=\s*"([\d.]+)', open_tag)
    if width and height:
        return float(width.group(1)), float(height.group(1))

    return default_w, default_h


def _namespace_ids(inner: str, prefix: str) -> str:
    """Prefix every id (and its references) so panels don't collide.

    Model panels reuse ids like ``bg`` for gradients; once several panels share
    one document those ids clash and only the last definition wins. Prefixing
    each panel's ids with a per-panel ``prefix`` keeps them independent.
    """
    ids = set(re.findall(r'\bid\s*=\s*"([^"]+)"', inner))
    for _id in ids:
        escaped = re.escape(_id)
        new = f"{prefix}{_id}"
        inner = re.sub(rf'\bid(\s*=\s*)"{escaped}"', rf'id\1"{new}"', inner)
        inner = re.sub(rf"url\(#{escaped}\)", f"url(#{new})", inner)
        inner = re.sub(rf'href(\s*=\s*)"#{escaped}"', rf'href\1"#{new}"', inner)
    return inner


def stitch_svgs(
    svgs,
    panel_width: int = PANEL_WIDTH,
    panel_height: int = PANEL_HEIGHT,
    overlap: int = OVERLAP,
) -> str:
    """Stack daily panels into one tall SVG.

    Each panel is scaled to ``panel_width`` x ``panel_height`` (so it still lines
    up even if the model returned a differently-sized SVG) and offset downward by
    ``panel_height - overlap`` per day, so consecutive panels overlap by
    ``overlap`` pixels. Later panels are drawn on top, matching the "today lies
    over yesterday" intent.
    """
    svgs = list(svgs)
    if not svgs:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{panel_width}" '
            f'height="0" viewBox="0 0 {panel_width} 0"></svg>'
        )

    step = panel_height - overlap
    total_height = step * (len(svgs) - 1) + panel_height

    layers = []
    for i, svg in enumerate(svgs):
        inner = _svg_inner(svg)
        inner = _namespace_ids(inner, f"d{i}_")
        src_w, src_h = _svg_dimensions(svg, panel_width, panel_height)
        scale_x = panel_width / src_w
        scale_y = panel_height / src_h
        y = i * step
        transform = f"translate(0,{y}) scale({scale_x:g},{scale_y:g})"
        layers.append(f'  <g transform="{transform}">\n{inner}\n  </g>')

    body = "\n".join(layers)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{panel_width}" height="{total_height}" '
        f'viewBox="0 0 {panel_width} {total_height}">\n{body}\n</svg>'
    )
