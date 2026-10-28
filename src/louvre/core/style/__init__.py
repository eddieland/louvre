"""Louvre's house style for artifacts (REQUIREMENTS U6): a stylesheet an agent may use, its guide, and starter pages.

It is Annotated's type and color (ui/DESIGN.md) made for a page inside the artifact's frame: dark first, light when the
reader's system is, every color a custom property. Its faces are Louvre's own, which Louvre serves at `FONTS_PATH`, the
one thing an artifact's sandbox lets it load; elsewhere, such as in canopy's local store, they fall back to the reader's
own serif and sans. Louvre wraps every Markdown artifact in it, and the `style_get` tool, the MCP server's resources,
and its `style` prompt hand it to an agent writing HTML, which inlines it in a `<style>` element. The version is in the
name: until 1.0 there is one, changed in place (D008); from 1.0 a later style is a new version, and never restyles a
page already published. A page that inlined a version keeps its stylesheet, but loads its version's faces from Louvre,
so Louvre serves every version's fonts for as long as a page may name them. A page Louvre draws itself, Markdown or
GeoJSON, is drawn whole each time it is shown, its markup and the current style together.

Each version's files sit in a directory named for it, beside this module: `style.css`, `rules.md`, the guide, a
starter page for each kind of artifact, which holds the line `/* style.css */` where the stylesheet goes, and `fonts/`,
each face's variable WOFF2 (Latin, from Fontsource) beside its Open Font License.
"""

from collections.abc import Mapping, Sequence
from enum import StrEnum
from importlib.resources import files

#: The style's name and version, as a page that uses it names it: the version handed to agents.
VERSION = "louvre-1"
#: Where Louvre serves the style's fonts, which its stylesheet's `@font-face` rules name.
FONTS_PATH = f"/style/{VERSION}/fonts/"


class Kind(StrEnum):
    """A kind of artifact the style has a starter page for."""

    #: Findings, with the numbers behind them.
    REPORT = "report"
    #: A choice between options, and the one recommended.
    DECISION = "decision"
    #: What will be done, in steps, with its risks and open questions.
    PLAN = "plan"
    #: Where something is, on a map drawn by the map kit.
    MAP = "map"


_ROOT = files(__name__)
_FILES = _ROOT / VERSION
#: Every version of the style, the current one among them: each directory beside this module named for one.
VERSIONS: Sequence[str] = sorted(d.name for d in _ROOT.iterdir() if d.is_dir() and d.name.startswith("louvre-"))
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
    Kind.MAP: "Where something is, on a map: regions, sites, a route, with what matters about each.",
}
#: Every version's fonts, by version and file name: the faces each version's stylesheet names, which Louvre serves at
#: that version's path for as long as a page may name them.
FONTS_BY_VERSION: Mapping[str, Mapping[str, bytes]] = {
    version: {
        f.name: f.read_bytes()
        for f in sorted((_ROOT / version / "fonts").iterdir(), key=lambda f: f.name)
        if f.name.endswith(".woff2")
    }
    for version in VERSIONS
}
#: The current style's fonts, by file name.
FONTS = FONTS_BY_VERSION[VERSION]
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
