"""Louvre's house style: the stylesheet, its guide, and the starter pages an agent writes from."""

import hashlib
import re
from importlib.resources import files

import pytest
from syrupy.assertion import SnapshotAssertion

from louvre.core import style

#: Every class the stylesheet styles.
STYLED = set(re.findall(r"\.(l-[a-z0-9-]+)", style.CSS))
#: The classes no starter page needs: another element for the page, and for a figure; a map's ramp, which the map
#: starter's key does without; and the features under a map Louvre draws from GeoJSON (louvre.core.geodata).
UNUSED = {"l-page", "l-figure", "l-ramp", "l-features"}


@pytest.mark.parametrize("kind", list(style.Kind))
def test_each_starter_page_inlines_the_stylesheet_once(kind: style.Kind) -> None:
    starter = style.STARTERS[kind]

    assert starter.count(style.CSS) == 1
    assert "/* style.css */" not in starter
    assert '<body class="louvre">' in starter


@pytest.mark.parametrize("kind", list(style.Kind))
def test_each_starter_page_loads_nothing_from_the_network(kind: style.Kind) -> None:
    assert not re.search(r'(src|href)="(https?:)?//', style.STARTERS[kind])
    assert "@import" not in style.STARTERS[kind]


def test_the_starter_pages_together_use_every_component_and_only_those() -> None:
    used = {
        name
        for starter in style.STARTERS.values()
        for names in re.findall(r'class="([^"]+)"', starter)
        for name in names.split()
    }

    assert used - {"louvre"} == STYLED - UNUSED


def test_the_guide_names_every_component_and_every_kind() -> None:
    assert {name for name in STYLED if name not in style.RULES} == set()
    assert {kind for kind in style.Kind if f"`{kind}`" not in style.RULES} == set()


def test_each_color_is_defined_for_both_themes() -> None:
    dark, _, light = style.CSS.partition("@media (prefers-color-scheme: light)")
    defined = set(re.findall(r"(--l-[a-z0-9]+):", dark))
    colors = {name for name in defined if re.search(rf"{name}: #", dark)}

    assert colors - set(re.findall(r"(--l-[a-z0-9]+):", light)) == set()


def test_the_handover_gives_the_starter_page_of_the_kind_asked_for() -> None:
    given = style.handover(style.Kind.PLAN)

    assert given["starter"] == style.STARTERS[style.Kind.PLAN]
    assert given["kinds"] == dict(style.KINDS)
    assert style.handover()["kind"] == style.Kind.REPORT


@pytest.mark.parametrize("version", style.VERSIONS)
def test_every_font_each_versions_stylesheet_names_is_one_louvre_serves(version: str) -> None:
    css = (files(style) / version / "style.css").read_text(encoding="utf-8")
    named = re.findall(r'url\("([^"]+)"\)', css)

    assert sorted(named) == sorted(f"/style/{version}/fonts/{name}" for name in style.FONTS_BY_VERSION[version])


def test_the_current_version_is_one_louvre_serves() -> None:
    assert style.VERSION in style.VERSIONS
    assert style.FONTS_BY_VERSION[style.VERSION] == style.FONTS
    assert f"/style/{style.VERSION}/fonts/" == style.FONTS_PATH


def test_no_versions_fonts_ever_change(snapshot: SnapshotAssertion) -> None:
    """Hold every version's fonts to their hashes, and every version to being served.

    A page loads its version's faces from Louvre, which tells browsers to keep them for a year: a changed or dropped
    font changes every page published with that version. Put a new font in a new version of the style instead.
    """
    hashes = {
        version: {name: hashlib.sha256(data).hexdigest() for name, data in fonts.items()}
        for version, fonts in style.FONTS_BY_VERSION.items()
    }

    assert hashes == snapshot
