"""Charts in the house style, drawn from their data: to the guide's rules, inside their box, and held by snapshots."""

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st
from syrupy.assertion import SnapshotAssertion

from louvre.core import style
from louvre.core.style.chart import HEIGHT, LARGEST, MOST_SERIES, WIDTH, Chart, Kind, Series, Target, figure
from louvre.core.style.check import check

#: A week of p95 checkout, against the week before and a target.
WEEK = Chart(
    Kind.LINE,
    "p95 checkout by day, in milliseconds",
    "p95 fell from 1,180 ms on Monday to 430 ms by Sunday",
    ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    [
        Series("This week", [1180, 1120, 720, 470, 440, 435, 430]),
        Series("Last week", [450, 470, 440, 460, 455, 450, 445]),
    ],
    Target("Target, 450 ms", 450),
)
#: A change by region, one of them below zero.
REGIONS = Chart(
    Kind.BAR,
    "Change in abandonment, by region, in points",
    "Abandonment fell in every region but sa-east",
    ["us-east", "eu-west", "ap-south", "sa-east"],
    [Series("Week 42", [-2.2, -2.8, -1.5, 0.4]), Series("Week 43", [-0.4, -0.1, -0.6, 1.2])],
)


def page(body: str) -> str:
    """Put `body` in a page in the house style that follows the guide.

    Returns:
        The page.
    """
    head = '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
    return (
        f'<!doctype html><html lang="en"><head>{head}<title>Charts</title><style>\n{style.CSS}</style></head>'
        f'<body class="louvre"><main><h1>Charts</h1>{body}</main></body></html>'
    )


@pytest.mark.parametrize("chart", [WEEK, REGIONS], ids=["line", "bar"])
def test_a_chart_is_drawn_as_it_was(chart: Chart, snapshot: SnapshotAssertion) -> None:
    assert figure(chart) == snapshot


@pytest.mark.parametrize("chart", [WEEK, REGIONS], ids=["line", "bar"])
def test_a_chart_in_a_page_follows_the_guide(chart: Chart) -> None:
    assert check(page(figure(chart))) == []


def test_its_axis_is_round_values_short_enough_to_fit() -> None:
    calls = Chart(
        Kind.BAR,
        "Tax calls a week",
        "Redis makes the fewest",
        ["Process", "Redis", "None"],
        [
            Series("Calls", [1_200_000, 190_000, 3_100_000]),
        ],
    )

    assert _axis(figure(WEEK)) == ["0", "500", "1,000", "1,500"]
    assert _axis(figure(REGIONS)) == ["\N{MINUS SIGN}3", "\N{MINUS SIGN}2", "\N{MINUS SIGN}1", "0", "1", "2"]
    assert _axis(figure(calls)) == ["0", "1M", "2M", "3M", "4M"]
    assert _axis(figure(Chart(Kind.LINE, "t", "d", ["a", "b"], [Series("s", [0, 90_000])]))) == [
        "0",
        "25k",
        "50k",
        "75k",
        "100k",
    ]


@pytest.mark.parametrize("values", [[1e-12, 3e-12], [0.1, 0.3], [0, 0], [-1e15, 1e15]])
def test_any_range_has_an_axis_of_distinct_values(values: list[float]) -> None:
    axis = _axis(figure(Chart(Kind.LINE, "t", "d", ["a", "b"], [Series("s", values)])))

    assert len(axis) == len(set(axis)) >= 2


def test_its_words_are_text_never_markup() -> None:
    drawn = figure(
        Chart(
            Kind.BAR,
            "<b>Calls</b>",
            'Say "fewer"',
            ["<i>a</i>"],
            [Series("<script>x</script>", [1])],
            Target("&", 1),
        ),
    )

    assert "<b>" not in drawn
    assert "<i>" not in drawn
    assert "<script>" not in drawn
    assert 'aria-label="Say &quot;fewer&quot;"' in drawn
    assert "<li>&amp;</li>" in drawn


def test_a_single_series_without_a_target_has_no_legend() -> None:
    assert "l-legend" not in figure(Chart(Kind.LINE, "Calls", "Fewer", ["a", "b"], [Series("Calls", [1, 2])]))


@pytest.mark.parametrize(
    ("chart", "says"),
    [
        (Chart(Kind.LINE, "t", "d", ["Mon"], [Series("s", [1])]), "2 to"),
        (Chart(Kind.BAR, "t", "d", [], [Series("s", [])]), "1 to"),
        (Chart(Kind.BAR, "t", "d", ["a"], []), "series"),
        (Chart(Kind.BAR, "t", "d", ["a"], [Series(str(i), [1]) for i in range(MOST_SERIES + 1)]), "small multiples"),
        (Chart(Kind.BAR, "t", "d", ["a", "b"], [Series("s", [1])]), "1 values for 2 labels"),
        (Chart(Kind.BAR, "t", "d", ["a"], [Series("s", [float("nan")])]), "finite"),
        (Chart(Kind.BAR, "t", "d", ["a"], [Series("s", [1])], Target("t", float("inf"))), "finite"),
        (Chart(Kind.BAR, "t", "d", ["a"], [Series("s", [-2e15])]), "at most"),
    ],
)
def test_data_it_cannot_draw_is_refused(chart: Chart, says: str) -> None:
    with pytest.raises(ValueError, match=says):
        figure(chart)


@given(
    st.sampled_from(Kind),
    st.integers(min_value=2, max_value=60).flatmap(
        lambda count: st.lists(
            st.lists(st.floats(min_value=-LARGEST, max_value=LARGEST), min_size=count, max_size=count),
            min_size=1,
            max_size=MOST_SERIES,
        ),
    ),
)
def test_every_mark_is_inside_the_chart(kind: Kind, values: list[list[float]]) -> None:
    labels = [f"L{i}" for i in range(len(values[0]))]
    drawn = figure(Chart(kind, "t", "d", labels, [Series(f"S{i}", v) for i, v in enumerate(values)]))

    xs = [float(x) for x in re.findall(r'\bx[12]?="(-?[\d.]+)"', drawn)]
    ys = [float(y) for y in re.findall(r'\by[12]?="(-?[\d.]+)"', drawn)]
    points = [float(n) for p in re.findall(r'points="([^"]+)"', drawn) for n in re.split(r"[ ,]", p)]
    assert all(0 <= x <= WIDTH for x in xs)
    assert all(0 <= y <= HEIGHT for y in ys)
    assert all(0 <= n <= WIDTH for n in points)


def _axis(drawn: str) -> list[str]:
    return re.findall(r'<text x="50" y="[\d.]+" text-anchor="end">([^<]+)</text>', drawn)
