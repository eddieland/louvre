"""Louvre's house style: the starter page an agent writes from."""

import re

from louvre.core import style


def test_the_starter_page_inlines_the_stylesheet_and_uses_each_component() -> None:
    classes = set(re.findall(r'class="([^"]+)"', style.STARTER))

    assert style.CSS in style.STARTER
    assert classes == {"louvre", "l-kicker", "l-lede", "l-kpis", "l-kpi", "l-callout"}
    assert "<figure>" in style.STARTER
    assert "<table>" in style.STARTER


def test_the_starter_page_loads_nothing_from_the_network() -> None:
    assert not re.search(r'(src|href)="(https?:)?//', style.STARTER)
    assert "@import" not in style.STARTER
