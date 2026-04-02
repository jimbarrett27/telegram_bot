"""LangChain tools for meme generation — one function per template."""

from langchain_core.tools import tool

from memes.renderer import render_meme

# Module-level result holder. The generator clears this before invoking
# the agent and reads it after the agent finishes.
last_render: tuple[bytes, str] | None = None


def _render(template_name: str, texts: dict[str, str]) -> str:
    global last_render
    img_bytes = render_meme(template_name, texts)
    last_render = (img_bytes, template_name)
    return f"Rendered {template_name} meme ({len(img_bytes)} bytes)"


@tool
def epic_handshake(left_arm: str, right_arm: str, handshake: str) -> str:
    """Two people firmly shaking hands, agreeing on something. The left and right arms are two different groups/people, and the handshake is what they unexpectedly agree on."""
    return _render("epic_handshake", {"left_arm": left_arm, "right_arm": right_arm, "handshake": handshake})


@tool
def woman_yelling_at_cat(woman: str, cat: str) -> str:
    """A woman angrily yelling/pointing at a confused cat sitting at a dinner table. The woman represents someone making an emotional accusation, and the cat represents the unbothered target of the accusation."""
    return _render("woman_yelling_at_cat", {"woman": woman, "cat": cat})


@tool
def distracted_boyfriend(other_woman: str, man: str, girlfriend: str) -> str:
    """A man turns to check out another woman while his girlfriend looks on disapprovingly. The man is being tempted by something new (other_woman) while neglecting what he already has (girlfriend)."""
    return _render("distracted_boyfriend", {"other_woman": other_woman, "man": man, "girlfriend": girlfriend})


@tool
def always_has_been(statement: str, always_has_been: str) -> str:
    """Two astronauts in space looking at Earth. One makes a surprising statement about what they see, and the other points a gun saying 'always has been' — revealing something was always true. The always_has_been text should almost always literally say 'Always has been', although similar phrases are sometimes appropriate as wordplay."""
    return _render("always_has_been", {"statement": statement, "always_has_been": always_has_been})


@tool
def the_same_picture(left_picture: str, right_picture: str) -> str:
    """Corporate needs you to find the difference between these two pictures — they're the same picture. Used when two obviously non equivalent things have been declared to be equivalent by mistake."""
    return _render("the_same_picture", {"left_picture": left_picture, "right_picture": right_picture})


@tool
def is_this_a(guy: str, butterfly: str, bottom_text: str) -> str:
    """A man (labelled as someone clueless) looks at a butterfly (labelled as something misidentified) and asks 'is this a ___?' — used for comically wrong identification or misunderstanding."""
    return _render("is_this_a", {"guy": guy, "butterfly": butterfly, "bottom_text": bottom_text})


@tool
def change_my_mind(statement: str) -> str:
    """A man sits at a table with a sign displaying a bold/controversial opinion, daring people to 'change my mind'. Used for hot takes and strong opinions, especially when those opinions are unjustifiably strong."""
    return _render("change_my_mind", {"statement": statement})


@tool
def grus_plan(top_left: str, top_right: str, bottom_left: str, bottom_right: str) -> str:
    """Gru from Despicable Me presents a plan on a whiteboard in 4 panels. The first two steps seem reasonable, but the third reveals an unintended consequence, and in the fourth panel Gru reacts in horror realising the flaw. The bottom two panels should have the same text — the unexpected bad outcome."""
    return _render("grus_plan", {"top_left": top_left, "top_right": top_right, "bottom_left": bottom_left, "bottom_right": bottom_right})


@tool
def off_ramp(straight_ahead: str, exit: str, car: str) -> str:
    """A car swerves off the highway at the last second to take an exit. 'straight_ahead' is the sensible/expected choice, 'exit' is the tempting alternative, and 'car' is who is making the bad decision."""
    return _render("off_ramp", {"straight_ahead": straight_ahead, "exit": exit, "car": car})


@tool
def drake(top: str, bottom: str) -> str:
    """Drake disapproves of the top text (something bad/boring) and enthusiastically approves of the bottom text (something better/funnier)."""
    return _render("drake", {"top": top, "bottom": bottom})


ALL_TOOLS = [
    epic_handshake,
    woman_yelling_at_cat,
    distracted_boyfriend,
    always_has_been,
    the_same_picture,
    is_this_a,
    change_my_mind,
    grus_plan,
    off_ramp,
    drake,
]
