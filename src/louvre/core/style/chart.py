"""Charts in the house style, drawn from their data (REQUIREMENTS U6).

A chart is a figure in the Marginalia look the operator chose (2026-10-24): what the chart is about in the accent, and
everything else in muted ink and hairlines; each series labeled where it is, so there is no legend; a title that says
the finding, over what is measured; moments that matter numbered on the chart, as Louvre numbers its threads, each
said in a sentence under it, where a reader can quote it in a comment; and its source. The SVG is 440 units wide and
its text is sized by the stylesheet, larger on a phone, where the chart is drawn smaller. It is markup only: no
script, and nothing to load.
"""

import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from html import escape
from itertools import pairwise
from typing import assert_never


class Kind(StrEnum):
    """A kind of chart."""

    #: Values in order, such as by day, as lines: the first series in the accent, the rest muted.
    LINE = "line"
    #: One value to each label, as bars across, the focus's in the accent.
    BAR = "bar"
    #: Each label's values side by side, as dots on one scale, such as before and after.
    DOT = "dot"


@dataclass(frozen=True)
class Series:
    """One series of values, one to each label."""

    #: What it is, as its label on the chart says, such as "this week".
    name: str
    values: Sequence[float]


@dataclass(frozen=True)
class Target:
    """A value to compare with, drawn as a dotted line across a line chart."""

    #: What it is, as its label on the chart says, such as "target".
    name: str
    value: float


@dataclass(frozen=True)
class Note:
    """A moment that matters, numbered on the chart and said under it."""

    #: The label of the point or row it is on.
    label: str
    #: What happened there, in a sentence.
    text: str


@dataclass(frozen=True)
class Chart:
    """What a chart shows, and how."""

    kind: Kind
    #: What the chart shows, in a sentence: its title, and what a reader who cannot see it is told.
    finding: str
    #: What is measured, and when, under the title, such as "p95 checkout, by day of week 43".
    measure: str
    #: Each point's or row's label, in order, such as a day.
    labels: Sequence[str]
    #: The series; the first is the one the chart is about.
    series: Sequence[Series]
    #: The values' unit, such as "ms" or "%", written after the largest value on the axis and each value on the chart.
    unit: str = ""
    #: A value to compare with, on a line chart.
    target: Target | None = None
    #: On a bar chart, the label whose bar is in the accent.
    focus: str | None = None
    notes: Sequence[Note] = ()
    #: Where the numbers come from.
    source: str = ""


#: The most series a chart has: more, and a reader cannot tell them apart.
MOST_SERIES = 4
#: The most labels a chart has.
MOST_LABELS = 60
#: The most notes a chart has: more, and none stands out.
MOST_NOTES = 9
#: The largest value a chart draws, either side of zero.
LARGEST = 1e15
#: The chart's width, in SVG units: 440, so its text reads on a phone and a laptop.
WIDTH = 440
#: About how wide a character of the chart's text is, in SVG units, to leave room for labels.
_CHAR = 7.2
#: The most labels written under a line chart: more would overlap, so some are skipped.
_WRITTEN = 7
#: The least space between two labels at the end of a line chart, in SVG units.
_LABEL_GAP = 15
#: A row's height in a bar or dot chart.
_ROW = 34
#: The longest line of markup a figure has before it is broken, leaving room for the indent of a line broken off.
_LINE = 112
#: A hollow mark's fill and stroke width: a point a note is on, or a series beside the first in a dot chart.
_HOLLOW = 'fill="var(--l-bg)" stroke-width="1.5"'
#: A hairline's width where it joins marks.
_THIN = 'stroke-width="1.5"'
#: A line chart's height, in SVG units.
_LINE_HEIGHT = 196.0
#: Where a dot chart's first row starts, below its series' names.
_DOT_TOP = 28.0


def figure(chart: Chart) -> str:
    """Draw a chart as a figure for a page in the house style.

    Returns:
        A `figure` element: the finding over the measure as its caption, the chart as an SVG labeled with the
        finding, the notes numbered as on the chart, and the source.

    Raises:
        ValueError: The data cannot be drawn: too few labels (a line needs two) or too many, no series or too many (a
            bar chart has one), a series without one value to each label, a value that is not a finite number or is
            past `LARGEST`, a focus or a note on a label the chart does not have, or too many notes.
    """
    for wrong, message in _problems(chart):
        if wrong:
            raise ValueError(message)
    noted = {chart.labels.index(n.label): i + 1 for i, n in enumerate(chart.notes)}
    match chart.kind:
        case Kind.LINE:
            height, drawn = _LINE_HEIGHT, list(_line(chart, noted))
        case Kind.BAR:
            height, drawn = len(chart.labels) * _ROW + 4, list(_bar(chart, noted))
        case Kind.DOT:
            height, drawn = _DOT_TOP + len(chart.labels) * _ROW + 26, list(_dot(chart, noted))
        case _:
            assert_never(chart.kind)
    lines = [
        '<figure class="l-plot">',
        f'<figcaption><span class="l-say">{escape(chart.finding)}</span>',
        f'<span class="l-measure">{escape(chart.measure)}</span></figcaption>',
        f'<svg class="l-chart" viewBox="0 0 {WIDTH} {height:g}" role="img">',
        f"<title>{escape(chart.finding.rstrip('.'))}. {escape(chart.measure)}</title>",
        *drawn,
        "</svg>",
        *(
            ['<ol class="l-notes">', *(f"<li>{escape(n.text)}</li>" for n in chart.notes), "</ol>"]
            if chart.notes
            else []
        ),
        *([f'<p class="l-source">{escape(chart.source)}</p>'] if chart.source else []),
        "</figure>",
    ]
    return "".join(_wrap(line) + "\n" for line in lines)


def _wrap(line: str) -> str:
    """Break a line of markup longer than `_LINE` at the spaces where a break changes nothing a reader sees.

    That is a space in text, between a tag's attributes, or between the points of a `points` attribute; never inside
    another attribute's value.

    Returns:
        The line, broken where it must be, each line after the first indented.
    """
    breaks: list[int] = []
    tag = quoted = False
    name = ""
    for i, c in enumerate(line):
        if quoted:
            quoted = c != '"'
            if quoted and c == " " and name == "points":
                breaks.append(i)
        elif tag and c == '"':
            quoted, name = True, line[: i - 1].rsplit(" ", 1)[-1]
        elif c in "<>":
            tag = c == "<"
        elif c == " ":
            breaks.append(i)
    out: list[str] = []
    start = 0
    while len(line) - start > _LINE:
        cut = max((b for b in breaks if start < b <= start + _LINE), default=None)
        if cut is None:
            break
        out.append(line[start:cut])
        start = cut + 1
    out.append(line[start:])
    return "\n    ".join(out)


def _problems(chart: Chart) -> Iterator[tuple[bool, str]]:
    """Look for what would keep a chart from being drawn.

    Yields:
        Each check: whether it fails, and what it says if it does.
    """
    fewest = 2 if chart.kind == Kind.LINE else 1
    yield (
        not fewest <= len(chart.labels) <= MOST_LABELS,
        f"a {chart.kind} chart has {fewest} to {MOST_LABELS} labels, not {len(chart.labels)}",
    )
    most = 1 if chart.kind == Kind.BAR else MOST_SERIES
    instead = "compare series with a dot chart" if chart.kind == Kind.BAR else "draw small multiples instead"
    yield (
        not 1 <= len(chart.series) <= most,
        f"a {chart.kind} chart has 1 to {most} series, not {len(chart.series)}: {instead}",
    )
    for s in chart.series:
        yield (
            len(s.values) != len(chart.labels),
            f"series {s.name!r} has {len(s.values)} values for {len(chart.labels)} labels",
        )
    yield (
        not all(math.isfinite(v) and abs(v) <= LARGEST for v in _values(chart)),
        f"every value is a finite number, at most {LARGEST:g} either side of zero",
    )
    yield chart.focus is not None and chart.focus not in chart.labels, f"the focus {chart.focus!r} is not a label"
    yield len(chart.notes) > MOST_NOTES, f"a chart has at most {MOST_NOTES} notes"
    for n in chart.notes:
        yield n.label not in chart.labels, f"a note is on {n.label!r}, which is not a label"


def _values(chart: Chart) -> list[float]:
    return [v for s in chart.series for v in s.values] + ([chart.target.value] if chart.target else [])


def _line(chart: Chart, noted: Mapping[int, int]) -> Iterator[str]:
    """Draw a line chart: gridlines labeled above, lines labeled at their ends, the first series in the accent.

    Yields:
        Each mark.
    """
    top, bottom = 24.0, _LINE_HEIGHT - 28
    ends = [s.name for s in chart.series] + ([chart.target.name] if chart.target else [])
    right = WIDTH - min(max(len(name) for name in ends) * _CHAR + 14, 130)
    values = _values(chart)
    ticks = _ticks(min(0.0, *values), max(0.0, *values))
    scale = _Scale(ticks[0], ticks[-1], bottom, top)
    count = len(chart.labels)
    # The lines start right of the values written over the gridlines, so the first point never runs into one.
    left = max(len(_number(t)) for t in ticks) * _CHAR + 10
    xs = [round(left + (right - left - 8) * i / (count - 1), 2) for i in range(count)]
    yield from _gridlines(ticks, scale, right, chart.unit)
    labels: list[tuple[float, str, str]] = []
    if chart.target is not None:
        y = scale(chart.target.value)
        yield f'<line x1="0" x2="{right:g}" y1="{y:g}" y2="{y:g}" stroke="var(--l-muted)" stroke-dasharray="1 3"/>'
        labels.append((y, chart.target.name, "var(--l-muted)"))
    for i, s in reversed(list(enumerate(chart.series))):
        color, width = ("var(--l-accent)", 2.25) if i == 0 else ("var(--l-muted)", 1.25)
        points = " ".join(f"{x:g},{scale(v):g}" for x, v in zip(xs, s.values, strict=True))
        yield (
            f'<polyline fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round" '
            f'stroke-linecap="round" points="{points}"/>'
        )
        labels.append((scale(s.values[-1]), s.name, color))
    focus = chart.series[0].values
    end = scale(focus[-1])
    yield f'<circle cx="{xs[-1]:g}" cy="{end:g}" r="3.5" fill="var(--l-accent)"/>'
    yield (
        f'<text class="l-value" x="{xs[-1]:g}" y="{end - 9:g}" text-anchor="end" fill="var(--l-accent)">'
        f"{_with_unit(focus[-1], chart.unit)}</text>"
    )
    for i, mark in sorted(noted.items()):
        y = scale(focus[i])
        yield f'<circle cx="{xs[i]:g}" cy="{y:g}" r="3" {_HOLLOW} stroke="var(--l-accent)"/>'
        yield f'<text class="l-mark" x="{xs[i] + 6:g}" y="{y - 7:g}">{mark}</text>'
    for y, name, color in _spread(labels, top, bottom):
        yield f'<text class="l-label" x="{right + 10:g}" y="{y + 4:g}" fill="{color}">{escape(name)}</text>'
    every = math.ceil(count / _WRITTEN)
    for i, (x, label) in enumerate(zip(xs, chart.labels, strict=True)):
        if i % every == 0 or i == count - 1:
            anchor = "start" if i == 0 else "end" if i == count - 1 else "middle"
            yield f'<text x="{x:g}" y="{_LINE_HEIGHT - 6:g}" text-anchor="{anchor}">{escape(label)}</text>'


def _bar(chart: Chart, noted: Mapping[int, int]) -> Iterator[str]:
    """Draw a bar chart: a row to each label, its name on the left and its value at its bar's end.

    Yields:
        Each mark.
    """
    values = chart.series[0].values
    names = min(max(len(label) for label in chart.labels) * _CHAR + 16, 160)
    room = max(len(_number(v)) + len(chart.unit) for v in values) * _CHAR + 30
    low, high = min(0.0, *values), max(0.0, *values)
    scale = _Scale(low, high if high > low else 1.0, names, WIDTH - room)
    zero = scale(0)
    if low < 0:
        yield f'<line x1="{zero:g}" x2="{zero:g}" y1="0" y2="{len(values) * _ROW:g}" stroke="var(--l-rule)"/>'
    for i, (label, value) in enumerate(zip(chart.labels, values, strict=True)):
        y = i * _ROW
        chosen = chart.focus == label
        left, right = sorted((zero, scale(value)))
        name = "var(--l-ink)" if chart.focus is None or chosen else "var(--l-muted)"
        yield f'<text class="l-name" x="0" y="{y + 21:g}" fill="{name}">{escape(label)}</text>'
        yield (
            f'<rect x="{left:g}" y="{y + 10:g}" width="{max(right - left, 1.5):.2f}" height="14" '
            f'fill="{"var(--l-accent)" if chosen else "var(--l-muted)"}" opacity="{1 if chosen else 0.6}"/>'
        )
        at, anchor = (right + 6, "start") if value >= 0 else (left - 6, "end")
        style = ' class="l-value" fill="var(--l-accent)"' if chosen else ""
        yield f'<text x="{at:g}" y="{y + 21:g}" text-anchor="{anchor}"{style}>{_with_unit(value, chart.unit)}</text>'
        if i in noted:
            past = at + (len(_number(value)) + len(chart.unit) + 1) * _CHAR if value >= 0 else right + 6
            yield f'<text class="l-mark" x="{past:g}" y="{y + 14:g}">{noted[i]}</text>'


def _dot(chart: Chart, noted: Mapping[int, int]) -> Iterator[str]:
    """Draw a dot chart: a row to each label, its values as dots on one scale, joined by a hairline.

    Yields:
        Each mark.
    """
    names = min(max(len(label) for label in chart.labels) * _CHAR + 16, 160)
    values = _values(chart)
    ticks = _ticks(min(values), max(values))
    scale = _Scale(ticks[0], ticks[-1], names + 8, WIDTH - 20)
    axis = _DOT_TOP + len(chart.labels) * _ROW
    for i, tick in enumerate(ticks):
        x = scale(tick)
        text = _with_unit(tick, chart.unit) if i == len(ticks) - 1 else _number(tick)
        yield f'<line x1="{x:g}" x2="{x:g}" y1="{_DOT_TOP - 6:g}" y2="{axis:g}" stroke="var(--l-rule)"/>'
        yield f'<text x="{x:g}" y="{axis + 18:g}" text-anchor="middle">{text}</text>'
    for row, label in enumerate(chart.labels):
        y = _DOT_TOP + row * _ROW + _ROW / 2
        xs = [scale(s.values[row]) for s in chart.series]
        yield f'<text class="l-name" x="0" y="{y + 5:g}" fill="var(--l-ink)">{escape(label)}</text>'
        yield f'<line x1="{min(xs):g}" x2="{max(xs):g}" y1="{y:g}" y2="{y:g}" stroke="var(--l-muted)" {_THIN}/>'
        for i, x in reversed(list(enumerate(xs))):
            yield (
                f'<circle cx="{x:g}" cy="{y:g}" r="4.5" fill="var(--l-accent)"/>'
                if i == 0
                else f'<circle cx="{x:g}" cy="{y:g}" r="4" {_HOLLOW} stroke="var(--l-muted)"/>'
            )
        if row in noted:
            yield f'<text class="l-mark" x="{xs[0] + 8:g}" y="{y - 6:g}">{noted[row]}</text>'
    yield from _key(chart.series, [scale(s.values[0]) for s in chart.series], _DOT_TOP - 12)


def _key(series: Sequence[Series], xs: Sequence[float], y: float) -> Iterator[str]:
    """Name each series above its dot in the first row, or, where the names would overlap, in a row from the left.

    Yields:
        Each name.
    """
    spans = sorted((x - len(s.name) * _CHAR / 2, x + len(s.name) * _CHAR / 2) for s, x in zip(series, xs, strict=True))
    apart = all(a[1] + 6 < b[0] for a, b in pairwise(spans)) and spans[0][0] >= 0
    at = 0.0
    for i, s in enumerate(series):
        color = "var(--l-accent)" if i == 0 else "var(--l-muted)"
        x, anchor = (xs[i], "middle") if apart else (at, "start")
        at += len(s.name) * _CHAR + 16
        yield f'<text class="l-label" x="{x:g}" y="{y:g}" text-anchor="{anchor}" fill="{color}">{escape(s.name)}</text>'


@dataclass(frozen=True)
class _Scale:
    """Maps a range of values to a range of positions."""

    low: float
    high: float
    start: float
    end: float

    def __call__(self, value: float) -> float:
        """Place a value.

        Returns:
            Its position, to two decimals.
        """
        return round(self.start + (value - self.low) / (self.high - self.low) * (self.end - self.start), 2)


def _gridlines(ticks: Sequence[float], scale: _Scale, right: float, unit: str) -> Iterator[str]:
    """Draw a line chart's gridlines, each value written above its line at the left, the top one with the unit.

    Yields:
        Each gridline, and each value.
    """
    for i, tick in enumerate(ticks):
        y = scale(tick)
        text = _with_unit(tick, unit) if i == len(ticks) - 1 else _number(tick)
        yield f'<line x1="0" x2="{right:g}" y1="{y:g}" y2="{y:g}" stroke="var(--l-rule)"/>'
        yield f'<text x="0" y="{y - 5:g}">{text}</text>'


def _spread(labels: Sequence[tuple[float, str, str]], top: float, bottom: float) -> list[tuple[float, str, str]]:
    """Move the labels at a line chart's end apart, keeping each as near its line as the others let it.

    Returns:
        The labels, top first, each at least `_LABEL_GAP` from the next.
    """
    placed = sorted(labels)
    ys = [y for y, *_ in placed]
    for i in range(1, len(ys)):
        ys[i] = max(ys[i], ys[i - 1] + _LABEL_GAP)
    if ys and ys[-1] > bottom:
        ys[-1] = bottom
        for i in range(len(ys) - 2, -1, -1):
            ys[i] = min(ys[i], ys[i + 1] - _LABEL_GAP)
    return [(max(y, top - 10), name, color) for y, (_, name, color) in zip(ys, placed, strict=True)]


def _ticks(low: float, high: float) -> list[float]:
    """Choose the axis's round values, from at or below `low` to at or above `high`.

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


def _with_unit(value: float, unit: str) -> str:
    """Write a value with its unit: a word's after a space that does not break, a sign's straight after.

    Returns:
        The value and its unit.
    """
    if not unit:
        return _number(value)
    return _number(value) + ("\N{NO-BREAK SPACE}" if unit[0].isalnum() else "") + escape(unit)


def _number(value: float) -> str:
    """Write a value as the chart shows it: short enough to fit, and no decimals it does not need.

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
