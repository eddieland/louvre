"""Charts in the house style, drawn from their data: in the Marginalia look, inside their box, held by snapshots."""

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st
from syrupy.assertion import SnapshotAssertion

from louvre.core import style
from louvre.core.style.chart import (
    LARGEST,
    MOST_NOTES,
    MOST_SERIES,
    WIDTH,
    Chart,
    Kind,
    Note,
    Series,
    Target,
    figure,
)
from louvre.core.style.check import check

#: A week of p95 checkout, against the week before and a target, with two moments noted.
WEEK = Chart(
    Kind.LINE,
    "Checkout fell under its target on Thursday, and stayed there",
    "p95 checkout, by day of week 43, against week 42",
    ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    [
        Series("this week", [1180, 1120, 720, 470, 440, 435, 430]),
        Series("last week", [450, 470, 440, 460, 455, 450, 445]),
    ],
    unit="ms",
    target=Target("target", 450),
    notes=[Note("Tue", "The tax fix ships."), Note("Thu", "Under the target for the first time since September.")],
    source="Checkout events, 19 to 25 October 2026",
)
#: Each option's tax calls, the one recommended in focus.
CALLS = Chart(
    Kind.BAR,
    "Redis makes a sixteenth of the tax calls of no cache at all",
    "Tax calls a week, replaying 22 October",
    ["In process", "Redis", "No cache"],
    [Series("calls", [1_200_000, 190_000, 3_100_000])],
    focus="Redis",
    notes=[Note("Redis", "Recommended: one small node.")],
)
#: Each region's abandonment, a week apart.
REGIONS = Chart(
    Kind.DOT,
    "Abandonment fell in every region but sa-east",
    "Abandoned at payment, by region, week 42 to week 43",
    ["us-east", "eu-west", "ap-south", "sa-east"],
    [Series("week 43", [7.9, 8.8, 8.4, 7.7]), Series("week 42", [10.1, 11.6, 9.9, 7.2])],
    unit="%",
    notes=[Note("sa-east", "Its fraud check moved a week later.")],
)
CHARTS = [WEEK, CALLS, REGIONS]
KINDS = ["line", "bar", "dot"]


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


@pytest.mark.parametrize("chart", CHARTS, ids=KINDS)
def test_a_chart_is_drawn_as_it_was(chart: Chart, snapshot: SnapshotAssertion) -> None:
    assert figure(chart) == snapshot


@pytest.mark.parametrize("chart", CHARTS, ids=KINDS)
def test_a_chart_in_a_page_follows_the_guide(chart: Chart) -> None:
    assert check(page(figure(chart))) == []


@pytest.mark.parametrize("chart", CHARTS, ids=KINDS)
def test_its_title_says_the_finding_over_the_measure_and_its_notes_are_numbered_as_on_the_chart(chart: Chart) -> None:
    drawn = " ".join(figure(chart).split())

    assert f'<span class="l-say">{chart.finding}</span>' in drawn
    assert f'<span class="l-measure">{chart.measure}</span>' in drawn
    assert re.findall(r'class="l-mark"[^>]*>(\d+)<', drawn) == [str(i + 1) for i in range(len(chart.notes))]
    assert re.findall(r"<li>([^<]+)</li>", drawn) == [n.text for n in chart.notes]


def test_one_accent_marks_what_the_chart_is_about() -> None:
    line, bar = figure(WEEK), figure(CALLS)

    assert re.findall(r'<polyline fill="none" stroke="([^"]+)"', line) == ["var(--l-muted)", "var(--l-accent)"]
    assert re.findall(r'<rect [^>]*fill="([^"]+)"', bar) == ["var(--l-muted)", "var(--l-accent)", "var(--l-muted)"]


def test_its_axis_is_round_values_short_enough_to_fit_with_the_unit_on_the_largest() -> None:
    nbsp = "\N{NO-BREAK SPACE}"

    assert _axis(figure(WEEK)) == ["0", "500", "1,000", f"1,500{nbsp}ms"]
    assert _axis(figure(Chart(Kind.LINE, "f", "m", ["a", "b"], [Series("s", [0, 90_000])]))) == [
        "0",
        "25k",
        "50k",
        "75k",
        "100k",
    ]
    assert ">190k<" in figure(CALLS)
    assert ">12%<" in figure(REGIONS)


@pytest.mark.parametrize("values", [[1e-12, 3e-12], [0.1, 0.3], [0, 0], [-1e15, 1e15]])
def test_any_range_has_an_axis_of_distinct_values(values: list[float]) -> None:
    axis = _axis(figure(Chart(Kind.LINE, "f", "m", ["a", "b"], [Series("s", values)])))

    assert len(axis) == len(set(axis)) >= 2


def test_its_words_are_text_never_markup() -> None:
    drawn = figure(
        Chart(
            Kind.BAR,
            "<b>Calls</b>",
            'Say "fewer"',
            ["<i>a</i>"],
            [Series("s", [1])],
            notes=[Note("<i>a</i>", "<script>x</script>")],
            source="A & B",
        ),
    )

    assert "<b>" not in drawn
    assert "<i>" not in drawn
    assert "<script>" not in drawn
    assert "Say &quot;fewer&quot;" in drawn
    assert "A &amp; B" in drawn


def test_a_chart_without_notes_or_a_source_has_neither() -> None:
    drawn = figure(Chart(Kind.LINE, "f", "m", ["a", "b"], [Series("s", [1, 2])]))

    assert "l-notes" not in drawn
    assert "l-source" not in drawn


@pytest.mark.parametrize(
    ("chart", "says"),
    [
        (Chart(Kind.LINE, "f", "m", ["Mon"], [Series("s", [1])]), "2 to"),
        (Chart(Kind.DOT, "f", "m", [], [Series("s", [])]), "1 to"),
        (Chart(Kind.DOT, "f", "m", ["a"], []), "series"),
        (Chart(Kind.DOT, "f", "m", ["a"], [Series(str(i), [1]) for i in range(MOST_SERIES + 1)]), "small multiples"),
        (Chart(Kind.BAR, "f", "m", ["a"], [Series("s", [1]), Series("t", [2])]), "dot chart"),
        (Chart(Kind.BAR, "f", "m", ["a", "b"], [Series("s", [1])]), "1 values for 2 labels"),
        (Chart(Kind.BAR, "f", "m", ["a"], [Series("s", [float("nan")])]), "finite"),
        (Chart(Kind.LINE, "f", "m", ["a", "b"], [Series("s", [1, 2])], target=Target("t", float("inf"))), "finite"),
        (Chart(Kind.BAR, "f", "m", ["a"], [Series("s", [-2e15])]), "at most"),
        (Chart(Kind.BAR, "f", "m", ["a"], [Series("s", [1])], focus="b"), "focus"),
        (Chart(Kind.BAR, "f", "m", ["a"], [Series("s", [1])], notes=[Note("b", "n")]), "not a label"),
        (Chart(Kind.BAR, "f", "m", ["a"], [Series("s", [1])], notes=[Note("a", "n")] * (MOST_NOTES + 1)), "notes"),
    ],
)
def test_data_it_cannot_draw_is_refused(chart: Chart, says: str) -> None:
    with pytest.raises(ValueError, match=says):
        figure(chart)


@given(
    st.sampled_from(Kind).flatmap(
        lambda kind: st.tuples(
            st.just(kind),
            st.integers(min_value=2, max_value=60).flatmap(
                lambda count: st.lists(
                    st.lists(st.floats(min_value=-LARGEST, max_value=LARGEST), min_size=count, max_size=count),
                    min_size=1,
                    max_size=1 if kind == Kind.BAR else MOST_SERIES,
                ),
            ),
        ),
    ),
)
def test_every_mark_is_inside_the_chart_and_every_line_fits(drawing: tuple[Kind, list[list[float]]]) -> None:
    kind, values = drawing
    labels = [f"label {i}" for i in range(len(values[0]))]
    drawn = figure(Chart(kind, "f " * 80, "m", labels, [Series(f"S{i}", v) for i, v in enumerate(values)], unit="ms"))
    [height] = re.findall(rf'viewBox="0 0 {WIDTH} ([\d.]+)"', drawn)

    xs = [float(x) for x in re.findall(r'\b(?:x[12]?|cx)="(-?[\d.]+)"', drawn)]
    ys = [float(y) for y in re.findall(r'\b(?:y[12]?|cy)="(-?[\d.]+)"', drawn)]
    points = [float(n) for p in re.findall(r'points="([^"]+)"', drawn) for n in re.split(r"[\s,]+", p.strip())]
    assert all(0 <= x <= WIDTH for x in xs + points[::2])
    assert all(0 <= y <= float(height) for y in ys + points[1::2])
    assert all(len(line) <= 120 for line in drawn.splitlines())


def _axis(drawn: str) -> list[str]:
    return re.findall(r'<text x="0" y="[\d.]+">([^<]+)</text>', drawn)
