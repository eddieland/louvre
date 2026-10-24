"""The tools agents call: the artifacts contract's eight, and Louvre's `style_get`.

Each is a request and what the store does with it. A tool's arguments are validated against its request, whose JSON
schema is its input schema; the store then does the call, held to its scope. What a tool returns is JSON: one object,
or for `comment_feed` one change to a line, its `end` line last, as canopy's connectors print. A refusal is the store's
`Refused`, which the server answers as a tool error carrying its code. These are canopy's own definitions
(packages/canopy-artifacts), so a skill written against canopy's local store works against Louvre unchanged.
"""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StrictBool, StrictInt, StrictStr

from louvre.core import style
from louvre.core.store import MAX_BODY, MAX_CONTENT, MAX_FEED, MAX_ORIGIN, Code, Refused, Store
from louvre.core.style import chart, check
from louvre.core.text import CONTEXT, Anchor, ContentType

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
    content_type: Annotated[ContentType, Field(description="text/html or text/markdown.")]
    content: Annotated[StrictStr, Field(description="The page, whole.")]
    origin: Origin = None
    artifact_id: Annotated[
        StrictStr | None,
        Field(description="To add a version to this artifact, which keeps its origin and its threads."),
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


class SeriesRequest(_Request):
    """One series of a chart's values."""

    name: Annotated[StrictStr, Field(description="What the series is, as its legend names it, such as This week.")]
    values: Annotated[list[FiniteFloat], Field(description="One value to each label, in the labels' order.")]


class TargetRequest(_Request):
    """A value to compare with, drawn as a dashed line."""

    name: Annotated[StrictStr, Field(description="What it is, as its legend names it, such as Target, 450 ms.")]
    value: FiniteFloat


class StyleChart(_Request):
    """Draw a chart in the house style."""

    kind: Annotated[chart.Kind, Field(description="line, for values over time; bar, for values side by side.")]
    title: Annotated[StrictStr, Field(description="What it shows, with its unit: the figure's caption.")]
    description: Annotated[
        StrictStr,
        Field(description="What it says, in words, for a reader who cannot see it: the finding, not 'a chart'."),
    ]
    labels: Annotated[
        list[StrictStr],
        Field(description=f"Each point's or bar's label, in order, such as a day: short, at most {chart.MOST_LABELS}."),
    ]
    series: Annotated[
        list[SeriesRequest],
        Field(description=f"1 to {chart.MOST_SERIES} series; the first is the one the chart is about."),
    ]
    target: Annotated[TargetRequest | None, Field(description="A value to compare with, if there is one.")] = None


class Resolve(_Request):
    """Resolve a thread, or reopen it."""

    thread_id: StrictStr
    resolved: Annotated[StrictBool, Field(description="true to resolve it, false to reopen it.")]


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
        "sandbox (a request to the network, storage, starter words left in) as errors, and what goes against the "
        "guide (no title or viewport, a chart without words, a width a phone cannot fit, a fixed color) as "
        "warnings. ok is true when nothing is an error. It reads the markup and runs no script.",
        StyleCheck,
        lambda _store, r: _checked(r.content),
    ),
    tool(
        "style_chart",
        "Draw a line or bar chart in the house style, from its data: a <figure> to paste into a page in the style, its "
        "caption the title, an inline SVG drawn to the guide's rules (round values on its axis, bars from zero, the "
        "style's series colors, so it works dark and light), and a legend. Say the chart's finding in the page's text "
        "too.",
        StyleChart,
        lambda _store, r: _charted(r),
    ),
)


def _checked(page: str) -> dict[str, object]:
    findings = check.check(page)
    return {
        "ok": not any(f.severity == check.Severity.ERROR for f in findings),
        "findings": [f.json() for f in findings],
    }


def _charted(request: StyleChart) -> dict[str, object]:
    drawn = chart.Chart(
        kind=request.kind,
        title=request.title,
        description=request.description,
        labels=request.labels,
        series=[chart.Series(s.name, s.values) for s in request.series],
        target=None if request.target is None else chart.Target(request.target.name, request.target.value),
    )
    try:
        return {"figure": chart.figure(drawn)}
    except ValueError as e:
        raise Refused(Code.INVALID, str(e)) from None
