"""Louvre's house style: the stylesheet, its guide, and the starter pages an agent writes from."""

import re

import pytest

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


def test_every_font_the_stylesheet_names_is_one_louvre_serves() -> None:
    named = re.findall(r'url\("([^"]+)"\)', style.CSS)

    assert sorted(named) == sorted(style.FONTS_PATH + name for name in style.FONTS)
