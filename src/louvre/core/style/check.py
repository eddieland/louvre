"""Check an HTML artifact against the house style's guide, before it is published (REQUIREMENTS U6).

It finds what of the guide a parser can see in the markup: what would not work in Louvre's sandbox (a request to the
network, the browser's storage, a class of the style without its stylesheet, a starter page's words left in), and
what a reader would miss or see badly (no title or viewport, a chart without words, words hidden in a closed
`details`, a width a phone cannot fit, a fixed color in a page in the style). It reads the markup with the stdlib's
parser and never runs it, so what a script draws it cannot see, and a page it passes may still read badly.
"""

import re
from collections.abc import Iterator, Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from enum import StrEnum
from html.parser import HTMLParser
from typing import override

from louvre.core import maps
from louvre.core.style import CSS, FONTS_PATH, STARTERS
from louvre.core.text import collapse, visible_text


class Severity(StrEnum):
    """How much a finding matters."""

    #: The page will not work in Louvre as written: fix it before publishing.
    ERROR = "error"
    #: The page works, but goes against the guide.
    WARNING = "warning"


class Rule(StrEnum):
    """What a finding is about."""

    #: Something the page loads, which the sandbox refuses.
    NETWORK = "network"
    #: A file the page names that is not beside it, or one beside it that nothing names (louvre.core.files).
    FILE = "file"
    #: The browser's storage, which the sandbox refuses.
    STORAGE = "storage"
    #: The style's classes without its stylesheet.
    STYLESHEET = "stylesheet"
    #: Words left from a starter page.
    PLACEHOLDER = "placeholder"
    #: What the page's head must say: its charset, viewport, title, and language.
    HEAD = "head"
    #: One `h1`, which says the finding.
    HEADING = "heading"
    #: A chart or other SVG without words for a reader who cannot see it.
    CHART = "chart"
    #: An image without alternative text.
    IMAGE = "image"
    #: Words a reader must open something to see.
    HIDDEN = "hidden"
    #: A width wider than a phone.
    WIDTH = "width"
    #: A fixed color, which shows in one theme only.
    COLOR = "color"
    #: A map: the map kit's script, and how many maps to a page.
    MAP = "map"


@dataclass(frozen=True)
class Finding:
    """One thing the page should change."""

    rule: Rule
    severity: Severity
    #: What is wrong, and what to do instead.
    message: str
    #: The markup or words it is about, cut short.
    excerpt: str = ""

    def json(self) -> dict[str, str]:
        """Give the finding as a tool returns it.

        Returns:
            Its rule, severity, message, and excerpt.
        """
        return {"rule": self.rule, "severity": self.severity, "message": self.message, "excerpt": self.excerpt}


#: The widest a box may be set, in CSS pixels: a small phone's screen.
PHONE = 360
#: The most of the markup a finding quotes.
EXCERPT = 80
#: Attributes whose value is fetched, on any element.
_FETCHED = frozenset({"src", "srcset", "poster", "data", "background", "xlink:href"})
#: Elements the policy loads from nowhere, inline or not at all: a script, a stylesheet, a frame, and a page's base.
_NEVER_LOADED = frozenset({"script", "link", "iframe", "frame", "object", "embed", "base"})
#: Elements whose `href` is fetched; a link's (`a`, `area`) is followed only when a reader clicks it.
_FETCHED_HREF = frozenset({"link", "image", "use", "feimage", "base"})
#: Scripts' ways out of the sandbox, which it refuses: a fetch from elsewhere than the page's own files, a socket, a
#: stream, and a beacon. A fetch of a relative path reads one of the page's files.
_NETWORK_API = re.compile(
    r"\bfetch\s*\(\s*['\"`](?:[a-z][a-z0-9+.-]*:|/)|\b(?:WebSocket|EventSource|navigator\.sendBeacon)\b",
    re.IGNORECASE,
)
_STORAGE_API = re.compile(r"\b(localStorage|sessionStorage|indexedDB|document\.cookie)\b")
#: In CSS: a URL, and an import, which loads a stylesheet from elsewhere.
_CSS_URL = re.compile(r"url\(\s*['\"]?([^'\")]*)['\"]?\s*\)", re.IGNORECASE)
_CSS_IMPORT = re.compile(r"@import\b[^;]*", re.IGNORECASE)
#: A URL's scheme, as `https:` or `mailto:`, and the schemes that load from the page itself.
_SCHEME = re.compile(r"[a-z][a-z0-9+.-]*:", re.IGNORECASE)
_INLINE = ("data:", "blob:")
#: In CSS: a width, or a minimum width, in pixels.
_CSS_WIDTH = re.compile(r"(?<![-\w])(?:min-)?width\s*:\s*(\d+(?:\.\d+)?)px", re.IGNORECASE)
#: A color written out, rather than one of the style's custom properties.
_FIXED_COLOR = re.compile(r"#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?|oklch|lab)\(", re.IGNORECASE)
#: SVG attributes that take a color.
_COLOR_ATTRIBUTES = frozenset({"fill", "stroke", "color", "stop-color", "flood-color", "lighting-color"})
#: Where Louvre serves a map kit, of any version, and the script a page loads of the one it serves.
_KITS = "/kit/"
_KIT_SCRIPT = f"{maps.PATH}map.js"
#: A map a script draws with the kit.
_DRAW = re.compile(r"\bLouvreMap\s*\.\s*draw\s*\(")
#: The most maps a page should draw: each holds a WebGL context, of which a phone keeps few, and the kit keeps one
#: drawn at a time on a phone.
MAX_MAPS = 1
#: The most coordinates a page's scripts should give its maps inline, beyond which a phone draws them slowly.
MAX_COORDINATES = 20_000
#: A coordinate, longitude and latitude, as GeoJSON writes one.
_COORDINATE = re.compile(r"\[\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*\]")
#: Whose basemap the kit draws, which a page with a map credits in its words: Natural Earth's, and OpenStreetMap's
#: streets, whose license asks for it.
BASEMAP_CREDITS = ("Natural Earth", "OpenStreetMap")
#: The credit a page gives them, as the guide has it.
BASEMAP_CREDIT = "Basemap: Natural Earth; streets © OpenStreetMap contributors."
#: A string in a script, which may name one of the page's files, as the kit's `data: "places.json"` does.
_QUOTED = re.compile(r"""(['"`])([^'"`\s]+)\1""")
#: The shortest run of a starter page's words that counts as left in: shorter ones, such as "Done", are any page's.
_PLACEHOLDER_LENGTH = 16


def check(page: str, files: AbstractSet[str] = frozenset()) -> list[Finding]:
    """Check an HTML page against the house style's guide, with `files`, the paths of the files published beside it.

    Returns:
        What it should change, errors first, each in the order the page has them.
    """
    read = _Page()
    read.feed(page)
    read.close()
    styles = [_authored(text) for text in read.styles]
    named = list(_named(read, styles))
    findings = [
        *_network(named, read),
        *_files(named, files, read),
        *_storage(read),
        *_maps(named, read, page),
        *_stylesheet(read),
        *_placeholders(page),
        *_head(read),
        *_headings(read),
        *read.findings,
        *_widths(read, styles),
        *_colors(read, styles),
    ]
    return sorted(findings, key=lambda f: f.severity != Severity.ERROR)


@dataclass(frozen=True)
class _Url:
    """A URL a page names."""

    url: str
    #: The markup or CSS it is in, cut short.
    excerpt: str
    #: Whether the page loads it, or only links to it.
    loaded: bool = True
    #: Whether the policy lets it load from the page's files: an image, a font, media, or data may; a script, a
    #: stylesheet, or a frame may not, from anywhere.
    from_files: bool = True

    def elsewhere(self) -> bool:
        """Tell whether it is somewhere other than the page and its files: a scheme's, or a path from the root.

        Returns:
            Whether it is.
        """
        if self.url.startswith((FONTS_PATH, _KITS)):
            # The house style's fonts, and the map kit, which Louvre serves to every page (D008); `_maps` checks
            # that a kit is one Louvre serves.
            return False
        inline = self.url.lower().startswith(_INLINE)
        return self.url.startswith("/") or (bool(_SCHEME.match(self.url)) and not inline)

    def relative(self) -> bool:
        """Tell whether it names one of the page's files: a path relative to the page.

        Returns:
            Whether it does.
        """
        return bool(self.url) and not self.url.startswith(("#", "/")) and not _SCHEME.match(self.url)

    def path(self) -> str:
        """Name the file it is: its path, without a query or a fragment.

        Returns:
            The path.
        """
        return self.url.split("#")[0].split("?")[0].removeprefix("./")


@dataclass(frozen=True)
class _Tag:
    name: str
    attrs: Mapping[str, str]
    #: The tag as the page has it.
    markup: str


class _Page(HTMLParser):
    """What `check` needs of a page, read once."""

    def __init__(self) -> None:
        """Start reading."""
        super().__init__(convert_charrefs=True)
        #: Every start tag, in order.
        self.tags: list[_Tag] = []
        #: The text of each `style` element.
        self.styles: list[str] = []
        #: The text of each `script` element, and each event handler's.
        self.scripts: list[str] = []
        #: The `title` element's text.
        self.title = ""
        #: What the reading found itself: SVGs without words, closed `details`, images without `alt`.
        self.findings: list[Finding] = []
        #: The element whose text is being read: `style`, `script`, or `title`.
        self._inside: str | None = None
        #: The SVGs open, outermost first, each with whether it has its words yet.
        self._svgs: list[tuple[_Tag, bool]] = []

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        read = _Tag(tag, values, self.get_starttag_text() or f"<{tag}>")
        self.tags.append(read)
        self.scripts.extend(value for name, value in values.items() if name.startswith("on"))
        if tag in {"style", "script", "title"}:
            self._inside = tag
            if tag == "style":
                self.styles.append("")
            elif tag == "script":
                self.scripts.append("")
        elif tag == "svg":
            self._svgs.append((read, values.get("aria-hidden") == "true" or bool(values.get("aria-label"))))
        elif tag == "img" and "alt" not in values:
            self.findings.append(
                Finding(
                    Rule.IMAGE,
                    Severity.WARNING,
                    'An image without alt: say what it shows in alt, or alt="" if it only decorates.',
                    _cut(read.markup),
                ),
            )
        elif tag == "details" and "open" not in values:
            self.findings.append(
                Finding(
                    Rule.HIDDEN,
                    Severity.WARNING,
                    "A closed <details> hides its words: a reader cannot see them at a glance or quote them in a "
                    "comment. Show them, or open it.",
                    _cut(read.markup),
                ),
            )

    @override
    def handle_endtag(self, tag: str) -> None:
        if tag == self._inside:
            self._inside = None
        elif tag == "svg" and self._svgs:
            svg, worded = self._svgs.pop()
            if not self._svgs and not worded:
                self.findings.append(
                    Finding(
                        Rule.CHART,
                        Severity.WARNING,
                        'An SVG without words for a reader who cannot see it: give it role="img" and an '
                        'aria-label that says what it shows, or aria-hidden="true" if it only decorates.',
                        _cut(svg.markup),
                    ),
                )

    @override
    def handle_data(self, data: str) -> None:
        match self._inside:
            case "style":
                self.styles[-1] += data
            case "script":
                self.scripts[-1] += data
            case "title" if not self._svgs:
                self.title += data
            case "title":
                self._svgs[0] = (self._svgs[0][0], self._svgs[0][1] or bool(data.strip()))
            case _:
                pass


def _authored(style: str) -> str:
    """Take the house style's stylesheet out of a `style` element's CSS.

    Returns:
        The page's own CSS.
    """
    return style.replace(CSS.rstrip(), "")


def _named(page: _Page, styles: Sequence[str]) -> Iterator[_Url]:
    """Find every URL the page loads, or links to: in its tags' attributes, and in its CSS.

    Yields:
        Each URL, where it is, and whether the page loads it.
    """
    for tag in page.tags:
        for name, value in tag.attrs.items():
            if name == "srcset":
                yield from (_Url(url.split()[0], _cut(tag.markup)) for url in value.split(",") if url.split())
            elif name in _FETCHED or (name == "href" and tag.name in _FETCHED_HREF):
                yield _Url(value.strip(), _cut(tag.markup), from_files=tag.name not in _NEVER_LOADED)
            elif name == "href" and tag.name in {"a", "area"}:
                yield _Url(value.strip(), _cut(tag.markup), loaded=False)
    for css in [*styles, *(tag.attrs["style"] for tag in page.tags if "style" in tag.attrs)]:
        for found in _CSS_URL.finditer(css):
            yield _Url(found.group(1), _cut(found.group()))
        for found in _CSS_IMPORT.finditer(css):
            # An import loads a stylesheet from elsewhere, whatever its URL says.
            yield _Url("//", _cut(found.group()))


def _network(named: Sequence[_Url], page: _Page) -> Iterator[Finding]:
    message = (
        "Louvre's sandbox loads nothing from elsewhere: this request is refused. Publish the file beside the page "
        "with files_publish and name it by its path, or put it in the page: an image as SVG markup or a data: URL, a "
        "script or stylesheet inline."
    )
    for named_url in named:
        kit = named_url.url.startswith(_KITS)
        if named_url.loaded and not kit and (named_url.elsewhere() or not named_url.from_files):
            yield Finding(Rule.NETWORK, Severity.ERROR, message, named_url.excerpt)
    for script in page.scripts:
        for found in _NETWORK_API.finditer(script):
            yield Finding(
                Rule.NETWORK,
                Severity.ERROR,
                "Louvre's sandbox has no network: a script reads only the files published beside its page.",
                _cut(found.group()),
            )


def _files(named: Sequence[_Url], files: AbstractSet[str], page: _Page) -> Iterator[Finding]:
    relative = [n for n in named if n.relative() and n.from_files]
    in_scripts = {found.group(2).removeprefix("./") for script in page.scripts for found in _QUOTED.finditer(script)}
    for n in relative:
        if n.path() not in files:
            yield Finding(
                Rule.FILE,
                Severity.ERROR,
                f"The page names {n.path()}, which is not among the files published beside it: publish it with "
                "files_publish, or name a file that is.",
                n.excerpt,
            )
    for path in sorted(files - {n.path() for n in relative} - in_scripts):
        yield Finding(Rule.FILE, Severity.WARNING, "A file published beside the page that nothing names.", path)


def _storage(page: _Page) -> Iterator[Finding]:
    for script in page.scripts:
        for found in _STORAGE_API.finditer(script):
            yield Finding(
                Rule.STORAGE,
                Severity.ERROR,
                "Louvre's sandbox has no storage: this throws. Keep the state in the script's own variables.",
                _cut(found.group()),
            )


def _maps(named: Sequence[_Url], page: _Page, markup: str) -> Iterator[Finding]:
    kits = [n for n in named if n.url.startswith(_KITS)]
    for n in kits:
        if n.path() != _KIT_SCRIPT:
            yield Finding(
                Rule.MAP,
                Severity.ERROR,
                f"Louvre serves no such map kit: load {_KIT_SCRIPT}, the kit's one script.",
                n.excerpt,
            )
    draws = sum(len(_DRAW.findall(script)) for script in page.scripts)
    if draws and not any(n.path() == _KIT_SCRIPT for n in kits):
        yield Finding(
            Rule.MAP,
            Severity.ERROR,
            f'The page draws a map without the map kit: load it first, with <script src="{_KIT_SCRIPT}"></script> '
            "in <head>.",
        )
    if not draws:
        return
    if not all(credit in visible_text(markup) for credit in BASEMAP_CREDITS):
        yield Finding(
            Rule.MAP,
            Severity.ERROR,
            f'The page draws a map without crediting its basemap: say "{BASEMAP_CREDIT}" in the figure\'s l-source.',
        )
    if not any("l-key" in _classes(tag) for tag in page.tags):
        yield Finding(
            Rule.MAP,
            Severity.WARNING,
            'A map without a key: say what the accent marks and what the rest are, in a <p class="l-key"> under it.',
        )
    if draws > MAX_MAPS:
        yield Finding(
            Rule.MAP,
            Severity.WARNING,
            f"The page draws {draws} maps: a phone keeps one drawn at a time, and a reader compares them only by "
            "scrolling. Draw one, with every place on it, and say the rest in a table.",
        )
    coordinates = sum(len(_COORDINATE.findall(script)) for script in page.scripts if _DRAW.search(script))
    if coordinates > MAX_COORDINATES:
        yield Finding(
            Rule.MAP,
            Severity.WARNING,
            f"The page's maps have {coordinates:,} coordinates inline, more than a phone draws well: simplify their "
            f"shapes to {MAX_COORDINATES:,} or fewer.",
        )


def _stylesheet(page: _Page) -> Iterator[Finding]:
    styled = any(name == "louvre" or name.startswith("l-") for tag in page.tags for name in _classes(tag))
    if styled and not any("--l-bg" in style for style in page.styles):
        yield Finding(
            Rule.STYLESHEET,
            Severity.ERROR,
            "The page uses the house style's classes without its stylesheet: inline what style_get returns as css "
            "in a <style> element in <head>.",
        )


def _placeholders(page: str) -> Iterator[Finding]:
    text = visible_text(page)
    for words in _starter_words():
        if words in text:
            yield Finding(
                Rule.PLACEHOLDER,
                Severity.ERROR,
                "Words left from a starter page, which say what goes in their place: replace them, or drop them.",
                _cut(words),
            )


def _head(page: _Page) -> Iterator[Finding]:
    def has(tag: str, **attrs: str) -> bool:
        return any(t.name == tag and all(t.attrs.get(k, "").lower() == v for k, v in attrs.items()) for t in page.tags)

    if not any(t.name == "meta" and "charset" in t.attrs for t in page.tags):
        yield Finding(Rule.HEAD, Severity.WARNING, 'No <meta charset="utf-8">: give the page one, first in <head>.')
    if not has("meta", name="viewport"):
        yield Finding(
            Rule.HEAD,
            Severity.WARNING,
            'No <meta name="viewport" content="width=device-width, initial-scale=1">: without it a phone shows the '
            "page at a laptop's width, too small to read.",
        )
    if not page.title.strip():
        yield Finding(Rule.HEAD, Severity.WARNING, "No <title>: give the page one that says what it is.")
    if not any(t.name == "html" and t.attrs.get("lang") for t in page.tags):
        yield Finding(Rule.HEAD, Severity.WARNING, 'No lang on <html>: say the page\'s language, such as lang="en".')


def _headings(page: _Page) -> Iterator[Finding]:
    count = sum(tag.name == "h1" for tag in page.tags)
    if count != 1:
        yield Finding(
            Rule.HEADING,
            Severity.WARNING,
            f"The page has {count} <h1> elements: give it one, which says the finding or the question, and <h2> for "
            "its sections.",
        )


def _widths(page: _Page, styles: Sequence[str]) -> Iterator[Finding]:
    for css in [*styles, *(tag.attrs["style"] for tag in page.tags if "style" in tag.attrs)]:
        for found in _CSS_WIDTH.finditer(css):
            if float(found.group(1)) > PHONE:
                yield Finding(
                    Rule.WIDTH,
                    Severity.WARNING,
                    f"A width wider than a small phone's {PHONE} px: the page scrolls sideways there. Use max-width, "
                    "a percentage, or the style's components, which wrap and stack.",
                    _cut(found.group()),
                )


def _colors(page: _Page, styles: Sequence[str]) -> Iterator[Finding]:
    if not any("louvre" in _classes(tag) for tag in page.tags if tag.name == "body"):
        return
    message = (
        "A fixed color in a page in the house style shows in one theme only: use the style's custom properties, "
        "such as var(--l-ink), var(--l-muted), or var(--l-accent)."
    )
    for css in [*styles, *(tag.attrs["style"] for tag in page.tags if "style" in tag.attrs)]:
        for found in _FIXED_COLOR.finditer(css):
            start = max(css.rfind(";", 0, found.start()), css.rfind("{", 0, found.start())) + 1
            yield Finding(Rule.COLOR, Severity.WARNING, message, _cut(css[start : found.end()]))
    for tag in page.tags:
        for name in _COLOR_ATTRIBUTES & tag.attrs.keys():
            if _FIXED_COLOR.search(tag.attrs[name]):
                yield Finding(Rule.COLOR, Severity.WARNING, message, _cut(tag.markup))


def _starter_words() -> list[str]:
    """Read the starter pages' words.

    Returns:
        Each run of their words long enough to count as left in, once.
    """
    found: dict[str, None] = {}
    for starter in STARTERS.values():
        read = _Words()
        read.feed(starter)
        read.close()
        found.update(dict.fromkeys(w for w in read.runs if len(w) >= _PLACEHOLDER_LENGTH))
    return list(found)


class _Words(HTMLParser):
    """Each run of a page's shown words between two tags."""

    def __init__(self) -> None:
        """Start reading."""
        super().__init__(convert_charrefs=True)
        self.runs: list[str] = []
        self._hidden = 0

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._hidden += tag in {"style", "script", "title", "svg"}

    @override
    def handle_endtag(self, tag: str) -> None:
        self._hidden -= tag in {"style", "script", "title", "svg"}

    @override
    def handle_data(self, data: str) -> None:
        if not self._hidden and (words := collapse(data)):
            self.runs.append(words)


def _classes(tag: _Tag) -> list[str]:
    return tag.attrs.get("class", "").split()


def _cut(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= EXCERPT else text[: EXCERPT - 1] + "…"
