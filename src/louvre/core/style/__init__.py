"""Louvre's house style for artifacts (REQUIREMENTS U6): a stylesheet an agent may use, its guide, and starter pages.

It is Annotated's type and color (ui/DESIGN.md) made for a page inside the artifact's frame: dark first, light when the
reader's system is, every color a custom property. A page cannot load fonts from the network in its sandbox, so it
names the faces and falls back to the reader's own serif and sans. Louvre wraps every Markdown artifact in it, and the
`style_get` tool, the MCP server's resources, and its `style` prompt hand it to an agent writing HTML, which inlines
it in a `<style>` element. The version is in the name: a later style is a new version, and never restyles a page
already published.

The style's files sit in a directory named for its version, beside this module: `style.css`, `rules.md`, the guide,
and a starter page for each kind of artifact, which holds the line `/* style.css */` where the stylesheet goes.
"""

from collections.abc import Mapping
from enum import StrEnum
from importlib.resources import files

#: The style's name and version, as a page that uses it names it.
VERSION = "louvre-1"


class Kind(StrEnum):
    """A kind of artifact the style has a starter page for."""

    #: Findings, with the numbers behind them.
    REPORT = "report"
    #: A choice between options, and the one recommended.
    DECISION = "decision"
    #: What will be done, in steps, with its risks and open questions.
    PLAN = "plan"


_FILES = files(__name__) / VERSION
#: Where a starter page's file puts the stylesheet.
_SLOT = "/* style.css */\n"

#: The stylesheet. Every class it styles starts `l-`, and the page's root takes `class="louvre"`.
CSS = (_FILES / "style.css").read_text(encoding="utf-8")
#: The guide to using it, for an agent: what `style_get` returns beside the stylesheet.
RULES = (_FILES / "rules.md").read_text(encoding="utf-8")
#: What each kind of artifact is for, as an agent choosing one reads it.
KINDS: Mapping[Kind, str] = {
    Kind.REPORT: "Findings, with the numbers behind them: a measurement, an investigation, a weekly review.",
    Kind.DECISION: "A choice between options, side by side, and the one recommended: a design or a vendor to pick.",
    Kind.PLAN: "What will be done, in steps, with its risks and open questions: a proposal, a migration, a rollout.",
}
#: A page to start from, by kind: the stylesheet inlined, and the components that kind uses, their words saying what
#: goes there.
STARTERS: Mapping[Kind, str] = {
    kind: (_FILES / f"{kind}.html").read_text(encoding="utf-8").replace(_SLOT, CSS, 1) for kind in Kind
}


def handover(kind: Kind = Kind.REPORT) -> dict[str, object]:
    """Hand the style to an agent, with the starter page for one kind of artifact.

    Returns:
        The version, the stylesheet, the guide, the kind asked for and its starter page, and every kind with what it
        is for.
    """
    return {
        "version": VERSION,
        "css": CSS,
        "rules": RULES,
        "kind": kind,
        "starter": STARTERS[kind],
        "kinds": dict(KINDS),
    }
