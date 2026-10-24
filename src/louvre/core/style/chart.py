"""Charts in the house style, drawn from their data (REQUIREMENTS U6).

A chart is a `figure` an agent puts in a page in the style: its caption, an inline SVG drawn to the guide's rules, and
a legend. The SVG is 440 units wide, so its text reads at a phone's width and a laptop's; its series take the style's
series colors in order, so it works in both themes; its value axis has a few round values and starts at zero unless a
value is below it; and it says what it shows in an `aria-label`, for a reader who cannot see it. It is markup only:
no script.
"""

import math
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from html import escape
from typing import assert_never


class Kind(StrEnum):
    """A kind of chart."""

    #: Values over time, or another order, as lines.
    LINE = "line"
    #: Values side by side, as bars from zero, grouped by label when there is more than one series.
    BAR = "bar"


@dataclass(frozen=True)
class Series:
    """One series of values, one to each label."""

    name: str
    values: Sequence[float]


@dataclass(frozen=True)
class Target:
    """A value to compare with, drawn as a dashed line across the chart."""

    name: str
    value: float


@dataclass(frozen=True)
class Chart:
    """What a chart shows, and how."""

    kind: Kind
    #: What it shows, with its unit: the figure's caption.
    title: str
    #: What it says, in words, for a reader who cannot see it: the SVG's `aria-label`.
    description: str
    #: Each point's or bar's label, in order, such as a day.
    labels: Sequence[str]
    series: Sequence[Series]
    target: Target | None = None


#: The most series a chart has: more, and a reader cannot tell them apart.
MOST_SERIES = 4
#: The most labels a chart has.
MOST_LABELS = 60
#: The largest value a chart draws, either side of zero.
LARGEST = 1e15
#: The chart's width and height, in SVG units: 440 wide, so its 14-unit text reads on a phone and a laptop.
WIDTH = 440
HEIGHT = 210
#: The plot's edges inside the SVG: room on the left for the value axis's labels, and below for the labels.
_LEFT, _RIGHT, _TOP, _BOTTOM = 56, 432, 12, 176
#: Where the labels' text sits, below the plot.
_LABEL_Y = 198
#: The most labels written under the chart: more would overlap, so some are skipped.
_WRITTEN = 6
#: Maps a value to its height in the SVG.
type _Scale = Callable[[float], float]


def figure(chart: Chart) -> str:
    """Draw a chart as a figure for a page in the house style.

    Returns:
        A `figure` element: the title as its caption, the chart as an SVG whose `aria-label` is the description, and
        a legend when there is more than one series or a target.

    Raises:
        ValueError: The data cannot be drawn: too few labels (a line needs two) or too many, no series or too many, a
            series without one value to each label, or a value that is not a finite number or is past `LARGEST`.
    """
    _check(chart)
    values = [v for s in chart.series for v in s.values] + ([chart.target.value] if chart.target else [])
    ticks = _ticks(min(0.0, *values), max(0.0, *values))

    def y(value: float) -> float:
        return round(_BOTTOM - (value - ticks[0]) / (ticks[-1] - ticks[0]) * (_BOTTOM - _TOP), 2)

    count = len(chart.labels)
    match chart.kind:
        case Kind.LINE:
            xs = [round(_LEFT + 10 + (_RIGHT - _LEFT - 16) * i / (count - 1), 2) for i in range(count)]
            marks, anchors = _lines(chart.series, xs, y), ["start", *["middle"] * (count - 2), "end"]
        case Kind.BAR:
            band = (_RIGHT - _LEFT) / count
            xs = [round(_LEFT + band * (i + 0.5), 2) for i in range(count)]
            marks, anchors = _bars(chart.series, xs, band, y), ["middle"] * count
        case _:
            assert_never(chart.kind)
    return (
        f"<figure>\n<figcaption>{escape(chart.title)}</figcaption>\n"
        f'<svg class="l-chart" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{escape(chart.description)}">\n'
        + "\n".join([*_axis(ticks, chart.target, y), *marks, *_labels(chart.labels, xs, anchors)])
        + f"\n</svg>\n{_legend(chart)}</figure>\n"
    )


def _check(chart: Chart) -> None:
    fewest = 2 if chart.kind == Kind.LINE else 1
    if not fewest <= len(chart.labels) <= MOST_LABELS:
        msg = f"a {chart.kind} chart has {fewest} to {MOST_LABELS} labels, not {len(chart.labels)}"
        raise ValueError(msg)
    if not 1 <= len(chart.series) <= MOST_SERIES:
        msg = f"a chart has 1 to {MOST_SERIES} series, not {len(chart.series)}: draw small multiples instead"
        raise ValueError(msg)
    for s in chart.series:
        if len(s.values) != len(chart.labels):
            msg = f"series {s.name!r} has {len(s.values)} values for {len(chart.labels)} labels"
            raise ValueError(msg)
    values = [v for s in chart.series for v in s.values] + ([chart.target.value] if chart.target else [])
    if not all(math.isfinite(v) and abs(v) <= LARGEST for v in values):
        msg = f"every value is a finite number, at most {LARGEST:g} either side of zero"
        raise ValueError(msg)


def _ticks(low: float, high: float) -> list[float]:
    """Choose the value axis's round values, from at or below `low` to at or above `high`.

    Returns:
        The values, lowest first, a round step apart; zero among them when the range spans it.
    """
    if high == low:
        high = low + 1
    raw = (high - low) / 4
    power = 10 ** math.floor(math.log10(raw))
    step = next(m * power for m in (1, 2, 2.5, 5, 10) if m * power >= raw)
    first = math.floor(low / step) * step
    last = math.ceil(high / step) * step
    # Each value is a whole number of steps, written to 12 digits, so 0.1 * 3 reads 0.3 and a tiny step stays above 0.
    return [float(f"{(first / step + i) * step:.12g}") for i in range(round((last - first) / step) + 1)]


def _axis(ticks: Sequence[float], target: Target | None, y: _Scale) -> Iterator[str]:
    for tick in ticks:
        dash = "" if tick == 0 else ' stroke-dasharray="2 4"'
        yield f'<line x1="{_LEFT}" y1="{y(tick):g}" x2="{_RIGHT}" y2="{y(tick):g}" stroke="var(--l-rule)"{dash}/>'
        yield f'<text x="{_LEFT - 6}" y="{y(tick) + 5:g}" text-anchor="end">{_number(tick)}</text>'
    if target is not None:
        yield (
            f'<line x1="{_LEFT}" y1="{y(target.value):g}" x2="{_RIGHT}" y2="{y(target.value):g}" '
            'stroke="var(--l-muted)" stroke-width="1.5" stroke-dasharray="5 4"/>'
        )


def _lines(series: Sequence[Series], xs: Sequence[float], y: _Scale) -> Iterator[str]:
    # The first series is drawn last, on top, and thickest: it is the one the chart is about.
    for i, s in reversed(list(enumerate(series))):
        points = " ".join(f"{x:g},{y(v):g}" for x, v in zip(xs, s.values, strict=True))
        yield (
            f'<polyline fill="none" stroke="var(--l-c{i + 1})" stroke-width="{3 if i == 0 else 2}" '
            f'stroke-linejoin="round" stroke-linecap="round" points="{points}"/>'
        )


def _bars(series: Sequence[Series], xs: Sequence[float], band: float, y: _Scale) -> Iterator[str]:
    # Each label's bars take most of its band, side by side, a hairline apart.
    width = band * 0.72 / len(series)
    for i, s in enumerate(series):
        for x, value in zip(xs, s.values, strict=True):
            top, bottom = sorted((y(value), y(0)))
            yield (
                f'<rect x="{x - band * 0.36 + width * i:.2f}" y="{top:g}" width="{max(width - 1, 1):.2f}" '
                f'height="{bottom - top:.2f}" fill="var(--l-c{i + 1})"/>'
            )


def _labels(labels: Sequence[str], xs: Sequence[float], anchors: Sequence[str]) -> Iterator[str]:
    every = math.ceil(len(labels) / _WRITTEN)
    for i, (x, label, anchor) in enumerate(zip(xs, labels, anchors, strict=True)):
        if i % every == 0 or i == len(labels) - 1:
            yield f'<text x="{x:g}" y="{_LABEL_Y}" text-anchor="{anchor}">{escape(label)}</text>'


def _legend(chart: Chart) -> str:
    if len(chart.series) == 1 and chart.target is None:
        return ""
    keys = [f'<li class="l-c{i + 1}">{escape(s.name)}</li>' for i, s in enumerate(chart.series)]
    if chart.target is not None:
        keys.append(f"<li>{escape(chart.target.name)}</li>")
    return '<ul class="l-legend">' + "".join(keys) + "</ul>\n"


def _number(value: float) -> str:
    """Write a value as its axis shows it: short enough to fit left of the plot, and no decimals it does not need.

    Returns:
        The value as text: thousands parted by commas up to 9,999, then in thousands (25k), millions (2.5M), and so
        on.
    """
    for least, size, suffix in ((1e12, 1e12, "T"), (1e9, 1e9, "B"), (1e6, 1e6, "M"), (1e4, 1e3, "k")):
        if abs(value) >= least:
            text = f"{value / size:,.4g}{suffix}"
            break
    else:
        text = f"{int(value):,}" if value == int(value) else f"{value:,.6g}"
    return text.replace("-", "\N{MINUS SIGN}")
