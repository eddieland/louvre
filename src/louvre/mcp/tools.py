"""The tools agents call: the contract's eight, and Louvre's own beside them.

Louvre's own are the style's, the decisions' five, `files_publish`, `map_publish`, and `board_publish`.

Each is a request and what the store does with it. A tool's arguments are validated against its request, whose JSON
schema is its input schema; the store then does the call, held to its scope. What a tool returns is JSON: one object,
or for `comment_feed` one change to a line, its `end` line last, as canopy's connectors print. A refusal is the store's
`Refused`, which the server answers as a tool error carrying its code. These are canopy's own definitions
(packages/canopy-artifacts), so a skill written against canopy's local store works against Louvre unchanged.
"""

import base64
import binascii
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StrictBool, StrictInt, StrictStr

from louvre.core import boards, geodata, style
from louvre.core import files as version_files
from louvre.core.decisions import MAX_ASKED, MAX_DETAIL, MAX_LABEL, MAX_OPTIONS, MAX_QUESTION, MIN_OPTIONS, Decisions
from louvre.core.decisions import Option as DecisionOption
from louvre.core.store import MAX_BODY, MAX_CONTENT, MAX_FEED, MAX_ORIGIN, Code, Refused, Store
from louvre.core.style import chart, check
from louvre.core.text import CONTEXT, Anchor, PageType

#: Origin pairs, by key, set when an artifact is made. Plain aliases, not `type` statements: pydantic leaves out the
#: description of a field whose type is a `type` alias.
Origin = Annotated[
    Mapping[StrictStr, StrictStr] | None,
    Field(description=f"At most {MAX_ORIGIN} string pairs, such as canopy.ticket, which a reader filters on."),
]
#: An origin a reader filters on.
OriginFilter = Annotated[
    Mapping[StrictStr, StrictStr] | None,
    Field(description="Only artifacts whose origin holds every one of these pairs."),
]


@dataclass(frozen=True)
class Tool:
    """One tool: its name, what it does, its request, and the call."""

    name: str
    #: What it does, for the model.
    description: str
    #: Its request, whose schema is the tool's input schema.
    request: type[BaseModel]
    #: Validate the arguments, and do the call in the store: what the tool returns, as text.
    call: Callable[[Mapping[str, object], Store], str]


def tool[R: BaseModel](name: str, description: str, request: type[R], do: Callable[[Store, R], object]) -> Tool:
    """Make `do` a tool, taking `request` as its arguments.

    Returns:
        The tool, which returns what `do` does as JSON: a list as one item to a line, anything else as one object.
    """

    def call(arguments: Mapping[str, object], store: Store) -> str:
        done = do(store, request.model_validate(arguments))
        if isinstance(done, list):
            return "\n".join(json.dumps(item, ensure_ascii=False) for item in done)
        return json.dumps(done, ensure_ascii=False)

    return Tool(name, description, request, call)


#: Each kind of artifact the house style has a starter page for, and what it is for.
_KINDS = " ".join(f"{kind}: {about}" for kind, about in style.KINDS.items())


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Publish(_Request):
    """Make an artifact, or add a version to one."""

    title: Annotated[StrictStr, Field(description="What the page is, in a few words.")]
    content_type: Annotated[PageType, Field(description="text/html or text/markdown.")]
    content: Annotated[StrictStr, Field(description="The page, whole.")]
    origin: Origin = None
    artifact_id: Annotated[
        StrictStr | None,
        Field(description="To add a version to this artifact, which keeps its origin and its threads."),
    ] = None


class FileRequest(_Request):
    """A file beside a version's content."""

    path: Annotated[
        StrictStr,
        Field(description="Where it is, relative to the page, as the page names it: p95.png, or data/regions.csv."),
    ]
    content_type: Annotated[version_files.Type, Field(description="What the file is.")]
    data: Annotated[
        StrictStr,
        Field(
            max_length=(version_files.MAX_FILE + 2) // 3 * 4,
            description=f"The file, base64-encoded: at most {version_files.MAX_FILE:,} bytes before encoding.",
        ),
    ]


class PublishWithFiles(Publish):
    """Make an artifact, or add a version to one, with files beside its content."""

    files: Annotated[
        list[FileRequest],
        Field(
            min_length=1,
            max_length=version_files.MAX_COUNT,
            description=f"The files the page names: at most {version_files.MAX_COUNT}, and "
            f"{version_files.MAX_FILES:,} bytes together.",
        ),
    ]


class MapPublish(_Request):
    """Make an artifact of GeoJSON, which Louvre draws as a map, or add a version to one."""

    title: Annotated[StrictStr, Field(description="The finding, in a few words, as the map's title.")]
    data: Annotated[
        dict[str, object],
        Field(
            description="A GeoJSON FeatureCollection, or one Feature (RFC 7946: [longitude, latitude], WGS 84), at "
            f"most {geodata.MAX_FEATURES:,} features. Each feature's properties are shown under the map and on a tap. "
            'An optional member "louvre" says how it is drawn: {"description": the finding in a sentence, "label": '
            'the property naming each feature (default "name"), "focus": {"property": P, "equals": [values]} for the '
            'features the map is about, in the accent, "ramp": {"property": a numeric P, "unit": "ms"} to color '
            'every feature by its value, "key": {"focus": what the accent marks, "rest": what the others are}}.',
        ),
    ]
    origin: Origin = None
    artifact_id: Annotated[
        StrictStr | None,
        Field(description="To add a version to this artifact, which keeps its origin and its threads."),
    ] = None


class FrameRequest(_Request):
    """An artifact on a board, at a screen's size."""

    artifact_id: Annotated[
        StrictStr,
        Field(description="An artifact you published; the frame shows its latest version."),
    ]
    label: Annotated[
        StrictStr,
        Field(
            description="What the frame is, beside the artifact's title, such as Phone, 390; at most "
            f"{boards.MAX_LABEL} characters.",
        ),
    ]
    width: Annotated[
        StrictInt,
        Field(
            ge=boards.MIN_WIDTH,
            le=boards.MAX_WIDTH,
            description="The width it is shown at, in CSS pixels, as a screen that wide shows the page: 390 for a "
            "phone, 1440 for a laptop.",
        ),
    ]
    height: Annotated[
        StrictInt,
        Field(
            ge=boards.MIN_HEIGHT,
            le=boards.MAX_HEIGHT,
            description="The height it is shown at, in CSS pixels: 844 for a phone, 900 for a laptop.",
        ),
    ]


class BoardPublish(_Request):
    """Make a board of artifacts, or publish one again."""

    title: Annotated[
        StrictStr,
        Field(description="What the board shows, in a few words, such as Checkout, three ways."),
    ]
    rows: Annotated[
        list[list[FrameRequest]],
        Field(
            min_length=1,
            description=f"The frames, a row at a time, left to right, at most {boards.MAX_FRAMES} in all; Louvre lays "
            "each row under the one before. A row a direction, each at a phone's and a laptop's size, shows a design "
            "study.",
        ),
    ]
    origin: Origin = None
    board_id: Annotated[
        StrictStr | None,
        Field(description="To publish this board again, with this title and these frames; it keeps its origin."),
    ] = None


class Read(_Request):
    """Read a version of an artifact."""

    artifact_id: StrictStr
    version: Annotated[StrictInt | None, Field(ge=1, description="The version; its latest when omitted.")] = None


class ListArtifacts(_Request):
    """List artifacts, newest first."""

    origin: OriginFilter = None
    cursor: Annotated[StrictStr | None, Field(description="The next_cursor of the page before.")] = None


class ThreadList(_Request):
    """List an artifact's threads."""

    artifact_id: StrictStr
    state: Annotated[Literal["open", "resolved"] | None, Field(description="Only threads in this state.")] = None
    version: Annotated[
        StrictInt | None,
        Field(ge=1, description="The version each anchor is looked for in; its latest when omitted."),
    ] = None


class Feed(_Request):
    """Read the changes to comments and threads after a cursor."""

    origin: OriginFilter = None
    since: Annotated[StrictInt, Field(description="The through of the last end line read; 0 for every change.")] = 0
    limit: Annotated[StrictInt, Field(description=f"The most changes to return, at most {MAX_FEED}.")] = MAX_FEED


class Reply(_Request):
    """Reply in a thread."""

    thread_id: StrictStr
    body: Annotated[StrictStr, Field(description=f"At most {MAX_BODY} characters.")]


class AnchorRequest(_Request):
    """A passage: a W3C Web Annotation TextQuoteSelector over a version's text, whitespace collapsed."""

    exact: Annotated[StrictStr, Field(description="The passage's words, as the version's text has them.")]
    prefix: Annotated[StrictStr, Field(description=f"Up to {CONTEXT} characters just before it.")] = ""
    suffix: Annotated[StrictStr, Field(description=f"Up to {CONTEXT} characters just after it.")] = ""


class Create(_Request):
    """Open a thread on a passage, or on the whole artifact."""

    artifact_id: StrictStr
    anchor: Annotated[
        AnchorRequest | None,
        Field(description="The passage, in the artifact's latest version; the whole artifact when omitted."),
    ] = None
    body: Annotated[StrictStr, Field(description=f"At most {MAX_BODY} characters.")]


class StyleGet(_Request):
    """Get Louvre's house style, with the starter page for one kind of artifact."""

    kind: Annotated[style.Kind, Field(description=f"The kind of artifact to start from. {_KINDS}")] = style.Kind.REPORT


class StyleCheck(_Request):
    """Check an HTML page against the house style's guide."""

    content: Annotated[
        StrictStr,
        Field(max_length=MAX_CONTENT, description="The page, whole, as it would be published."),
    ]
    files: Annotated[
        list[StrictStr],
        Field(
            max_length=version_files.MAX_COUNT,
            description="The paths of the files you will publish beside it with files_publish, if any.",
        ),
    ] = []


class SeriesRequest(_Request):
    """One series of a chart's values."""

    name: Annotated[StrictStr, Field(description="What it is, as its label on the chart says, such as this week.")]
    values: Annotated[list[FiniteFloat], Field(description="One value to each label, in the labels' order.")]


class TargetRequest(_Request):
    """A value to compare with, drawn as a dotted line."""

    name: Annotated[StrictStr, Field(description="What it is, as its label on the chart says, such as target.")]
    value: FiniteFloat


class NoteRequest(_Request):
    """A moment that matters, numbered on the chart and said under it."""

    label: Annotated[StrictStr, Field(description="The label of the point or row it is on.")]
    text: Annotated[StrictStr, Field(description="What happened there, in a sentence a reader can quote.")]


class StyleChart(_Request):
    """Draw a chart in the house style."""

    kind: Annotated[
        chart.Kind,
        Field(
            description="line, for values in order, such as by day; bar, for one value to each label; dot, for each "
            "label's values side by side, such as before and after.",
        ),
    ]
    finding: Annotated[
        StrictStr,
        Field(description="What the chart shows, in a sentence: its title, such as Checkout fell under its target."),
    ]
    measure: Annotated[
        StrictStr,
        Field(description="What is measured, and when, under the title, such as p95 checkout, by day of week 43."),
    ]
    labels: Annotated[
        list[StrictStr],
        Field(description=f"Each point's or row's label, in order: short, at most {chart.MOST_LABELS}."),
    ]
    series: Annotated[
        list[SeriesRequest],
        Field(
            description=f"The first is the one the chart is about, in the accent; at most {chart.MOST_SERIES}, one "
            "for a bar chart.",
        ),
    ]
    unit: Annotated[StrictStr, Field(description="The values' unit, such as ms or %.")] = ""
    target: Annotated[TargetRequest | None, Field(description="A value to compare with, on a line chart.")] = None
    focus: Annotated[
        StrictStr | None,
        Field(description="On a bar chart, the label whose bar is in the accent, such as the option recommended."),
    ] = None
    notes: Annotated[
        list[NoteRequest],
        Field(description=f"Moments that matter, at most {chart.MOST_NOTES}, numbered on the chart and said under it."),
    ] = []
    source: Annotated[StrictStr, Field(description="Where the numbers come from.")] = ""


class Resolve(_Request):
    """Resolve a thread, or reopen it."""

    thread_id: StrictStr
    resolved: Annotated[StrictBool, Field(description="true to resolve it, false to reopen it.")]


class PlaceRequest(_Request):
    """A place on the map of an artifact published with map_publish: one of its features, a point, or a box."""

    kind: Annotated[geodata.PlaceKind, Field(description="A feature of the data, a point, or a box.")]
    id: Annotated[
        StrictStr,
        Field(description="A feature's id: its GeoJSON id, or without one its label. Empty for a point or a box."),
    ] = ""
    coordinates: Annotated[
        Sequence[FiniteFloat],
        Field(description="A point's [longitude, latitude], or a box's [west, south, east, north], in WGS 84."),
    ] = ()


class OptionRequest(_Request):
    """One option a decision offers."""

    label: Annotated[StrictStr, Field(description=f"What it is, in a few words; at most {MAX_LABEL} characters.")]
    detail: Annotated[StrictStr, Field(description=f"A line more about it; at most {MAX_DETAIL} characters.")] = ""
    anchor: Annotated[
        AnchorRequest | None,
        Field(description="The passage of the artifact's latest version it is about, shown beside it."),
    ] = None
    place: Annotated[
        PlaceRequest | None,
        Field(
            description="Instead of a passage, the place on the map of a map_publish artifact's latest version it is "
            "about, lit on the map beside it; its anchor is then the place's words.",
        ),
    ] = None


class DecisionCreate(_Request):
    """Ask people a question on an artifact, to answer by choosing."""

    artifact_id: StrictStr
    question: Annotated[StrictStr, Field(description=f"What to decide; at most {MAX_QUESTION} characters.")]
    options: Annotated[
        Sequence[OptionRequest],
        Field(
            description=f"The choices, {MIN_OPTIONS} to {MAX_OPTIONS}, in the order shown; their ids are o1, o2, ...",
        ),
    ]
    multiple: Annotated[StrictBool, Field(description="Whether an answer may choose more than one option.")] = False
    asked: Annotated[
        Sequence[StrictStr],
        Field(
            description=f"The logins of the people whose answers are wanted, at most {MAX_ASKED}; anyone may answer.",
        ),
    ] = ()


class DecisionList(_Request):
    """List decisions, newest first."""

    artifact_id: Annotated[StrictStr | None, Field(description="Only this artifact's.")] = None
    origin: OriginFilter = None
    state: Annotated[Literal["open", "closed"] | None, Field(description="Only decisions in this state.")] = None


class DecisionRead(_Request):
    """Read one decision, with every answer."""

    decision_id: StrictStr


class DecisionClose(_Request):
    """Close a decision."""

    decision_id: StrictStr
    outcome: Annotated[StrictStr | None, Field(description="The id of the option decided on, if one was.")] = None
    note: Annotated[StrictStr, Field(description=f"Why, for its readers; at most {MAX_BODY} characters.")] = ""


class DecisionFeed(_Request):
    """Read the events on decisions after a cursor."""

    origin: OriginFilter = None
    since: Annotated[StrictInt, Field(description="The through of the last end line read; 0 for every event.")] = 0
    limit: Annotated[StrictInt, Field(description=f"The most events to return, at most {MAX_FEED}.")] = MAX_FEED


TOOLS = (
    tool(
        "artifact_publish",
        "Publish a page for people to read and comment on: a new artifact, or with artifact_id a new version of one, "
        "whose threads carry over by their passages' words.",
        Publish,
        lambda store, r: store.publish(
            title=r.title,
            content_type=r.content_type,
            content=r.content,
            origin=r.origin,
            artifact_id=r.artifact_id,
        ),
    ),
    tool(
        "artifact_read",
        "Read a version of an artifact: its metadata, its content, and its text, which anchors are taken from.",
        Read,
        lambda store, r: store.read(r.artifact_id, r.version),
    ),
    tool(
        "artifact_list",
        "List artifacts, newest first, a page at a time; pass next_cursor for the next page.",
        ListArtifacts,
        lambda store, r: store.artifacts(r.origin, r.cursor),
    ),
    tool(
        "thread_list",
        "List an artifact's threads with their comments, and whether each thread's passage is found in a version or "
        "gone from it (passage_gone).",
        ThreadList,
        lambda store, r: store.threads(r.artifact_id, state=r.state, version=r.version),
    ),
    tool(
        "comment_feed",
        "Read the changes to comments and threads after since, oldest first, one JSON object to a line, ending with "
        '{"kind": "end", "through": SEQ}: pass that SEQ as since for the next page. A page without its end line is '
        "incomplete.",
        Feed,
        lambda store, r: store.feed(r.origin, r.since, r.limit),
    ),
    tool(
        "comment_reply",
        "Reply in a thread.",
        Reply,
        lambda store, r: store.reply(r.thread_id, r.body),
    ),
    tool(
        "comment_create",
        "Comment on a passage of an artifact's latest version, quoted by its words and the text either side, or on "
        "the whole artifact: a new open thread.",
        Create,
        lambda store, r: store.comment(
            r.artifact_id,
            None if r.anchor is None else Anchor.of(r.anchor.exact, r.anchor.prefix, r.anchor.suffix),
            r.body,
        ),
    ),
    tool(
        "thread_resolve",
        "Resolve a thread, or reopen one.",
        Resolve,
        lambda store, r: store.resolve(r.thread_id, resolved=r.resolved),
    ),
    tool(
        "style_get",
        "Get Louvre's house style, optional: a stylesheet to inline in an HTML artifact so it looks like Louvre's own "
        "pages, dark and light, its guide to the page's shape, components, charts, and writing for comments, and a "
        "starter page for the kind of artifact asked for. A Markdown artifact is shown in it already.",
        StyleGet,
        lambda _store, r: style.handover(r.kind),
    ),
    tool(
        "style_check",
        "Check an HTML page against the house style's guide before publishing it: what would not work in Louvre's "
        "sandbox (a request to the network, a file it names that is not among files, storage, starter words left "
        "in) as errors, and what goes against the guide (no title or viewport, a chart without words, a width a phone "
        "cannot fit, a fixed color, a file nothing names) as warnings. ok is true when nothing is an error. It reads "
        "the markup and runs no script.",
        StyleCheck,
        lambda _store, r: _checked(r.content, r.files),
    ),
    tool(
        "style_chart",
        "Draw a line, bar, or dot chart in the house style, from its data: a <figure> to paste into a page in the "
        "style. Its title says the finding, over what is measured; the series it is about is in the accent and the "
        "rest in muted ink, each labeled where it is; moments that matter are numbered on it and said in notes under "
        "it, which readers can quote in comments; and its source closes it. It works dark and light, on a phone and a "
        "laptop.",
        StyleChart,
        lambda _store, r: _charted(r),
    ),
    tool(
        "decision_create",
        "Ask people to decide something about an artifact by choosing among options, rather than in a comment: which "
        "direction to take, whether to ship. An option may point at a passage, or at a place on a map_publish map. "
        "Name the people whose answers you want in asked. People answer on the artifact's page; read their answers "
        "with decision_read or decision_feed.",
        DecisionCreate,
        lambda store, r: Decisions(store).ask(
            r.artifact_id,
            r.question,
            [
                DecisionOption(
                    o.label,
                    o.detail,
                    None if o.anchor is None else Anchor.of(o.anchor.exact, o.anchor.prefix, o.anchor.suffix),
                    None if o.place is None else geodata.Pick(o.place.kind, o.place.id, o.place.coordinates),
                )
                for o in r.options
            ],
            multiple=r.multiple,
            asked=r.asked,
        ),
    ),
    tool(
        "decision_list",
        "List decisions, newest first, with each option's count and every answer: on one artifact, or on artifacts "
        "whose origin holds the pairs given.",
        DecisionList,
        lambda store, r: Decisions(store).listed(artifact_id=r.artifact_id, origin=r.origin, state=r.state),
    ),
    tool(
        "decision_read",
        "Read a decision: its question, its options each with how many chose it, who was asked and who answered, "
        "each answer with its note, and whether it is closed and on which option.",
        DecisionRead,
        lambda store, r: Decisions(store).read(r.decision_id),
    ),
    tool(
        "decision_close",
        "Close a decision you asked once it is decided, naming the option decided on, if one was; it takes no more "
        "answers.",
        DecisionClose,
        lambda store, r: Decisions(store).close(r.decision_id, r.outcome, r.note),
    ),
    tool(
        "decision_feed",
        "Read the events on decisions after since, oldest first, one JSON object to a line: decision_asked, "
        "decision_answered (an answer, or an answer changed, with its choices and note), and decision_closed. The "
        'last line is {"kind": "end", "through": SEQ}: pass that SEQ as since for the next page.',
        DecisionFeed,
        lambda store, r: Decisions(store).feed(r.origin, r.since, r.limit),
    ),
    tool(
        "files_publish",
        "Publish a page with files beside it, such as its images, a font, or the data behind a chart (CSV or JSON): "
        "artifact_publish's arguments and the files, each a path relative to the page, a type, and its bytes. The "
        'page names each file by its path (<img src="p95.png">), and loads it, and nothing else, from Louvre. A '
        "version's files are as fixed as its content: a revision publishes its files again, and an unchanged one costs "
        "nothing to keep.",
        PublishWithFiles,
        lambda store, r: store.publish(
            title=r.title,
            content_type=r.content_type,
            content=r.content,
            origin=r.origin,
            artifact_id=r.artifact_id,
            files=[version_files.File(f.path, f.content_type, _decoded(f.data, f.path)) for f in r.files],
        ),
    ),
    tool(
        "map_publish",
        "Publish GeoJSON, which Louvre draws as a map in its house style: the features, on a basemap from the whole "
        "earth down to a few streets, and under the map each feature's label and properties, which people read, tap "
        "on the map, and comment on. A revision is a new version with the same artifact_id; a thread on a feature's "
        "words stays on them while they hold. For a page with a map among other things, write HTML with the map kit "
        "instead (style_get, kind map).",
        MapPublish,
        lambda store, r: store.publish(
            title=r.title,
            content_type="application/geo+json",
            content=json.dumps(r.data, ensure_ascii=False, separators=(",", ":")),
            origin=r.origin,
            artifact_id=r.artifact_id,
        ),
    ),
    tool(
        "board_publish",
        "Put artifacts you published side by side on a board, a canvas people pan and zoom across, such as a design "
        "study's directions each at a phone's and a laptop's size: rows of frames, each an artifact's latest version "
        "shown at a size, under a label. People open a frame to read its artifact and comment on it, so its threads "
        "are the artifact's. It returns the board's url. Publishing it again with its board_id replaces its title and "
        "frames.",
        BoardPublish,
        lambda store, r: boards.Boards(store).publish(
            title=r.title,
            rows=[[boards.Framed(f.artifact_id, f.label, f.width, f.height) for f in row] for row in r.rows],
            origin=r.origin,
            board_id=r.board_id,
        ),
    ),
)


def _checked(page: str, named: Iterable[str]) -> dict[str, object]:
    findings = check.check(page, frozenset(named))
    return {
        "ok": not any(f.severity == check.Severity.ERROR for f in findings),
        "findings": [f.json() for f in findings],
    }


def _charted(request: StyleChart) -> dict[str, object]:
    drawn = chart.Chart(
        kind=request.kind,
        finding=request.finding,
        measure=request.measure,
        labels=request.labels,
        series=[chart.Series(s.name, s.values) for s in request.series],
        unit=request.unit,
        target=None if request.target is None else chart.Target(request.target.name, request.target.value),
        focus=request.focus,
        notes=[chart.Note(n.label, n.text) for n in request.notes],
        source=request.source,
    )
    try:
        return {"figure": chart.figure(drawn)}
    except ValueError as e:
        raise Refused(Code.INVALID, str(e)) from None


def _decoded(data: str, path: str) -> bytes:
    try:
        return base64.b64decode(data, validate=True)
    except binascii.Error:
        raise Refused(Code.INVALID, f"{path}'s data is not base64") from None
