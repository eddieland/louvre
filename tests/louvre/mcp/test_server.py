"""The MCP server answers the contract's tools as canopy's local store does, and Louvre's own, to the SDK's client."""

import base64
import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import mcp
import pytest
from anyio.from_thread import BlockingPortal, start_blocking_portal
from mcp.shared.exceptions import MCPError
from mcp.types import CallToolResult, TextContent, TextResourceContents

from louvre.core import accounts, style
from louvre.core.db import Connection
from louvre.core.decisions import Decisions
from louvre.core.store import MAX_BODY, MAX_FEED, MAX_ORIGIN, Store
from louvre.mcp import server
from tests.conftest import MakeAgent, person

#: A report: the passage people comment on sits in markup.
REPORT = """<html><head><title>Cache report</title></head><body>
<h1>Cache report</h1>
<p>The cache is <em>slow</em> under load, because every miss takes the lock.</p>
<p>We should shard it.</p>
</body></html>"""
#: The report's next version: the first passage kept word for word, the second reworded.
REVISED = """<html><body>
<h1>Cache report, revised</h1>
<p>Measured again: the cache is slow under load, because every miss takes the lock.</p>
<p>Sharding it is the plan.</p>
</body></html>"""
#: The contract's eight tools, then Louvre's own.
TOOLS = [
    "artifact_publish",
    "artifact_read",
    "artifact_list",
    "thread_list",
    "comment_feed",
    "comment_reply",
    "comment_create",
    "thread_resolve",
    "style_get",
    "style_check",
    "style_chart",
    "decision_create",
    "decision_list",
    "decision_read",
    "decision_close",
    "decision_feed",
    "files_publish",
    "map_publish",
    "board_publish",
]


class Client:
    """Calls a store's tools through the MCP server, with the SDK's client, in process."""

    def __init__(self, portal: BlockingPortal, session: mcp.Client) -> None:
        """Call through `session`, connected in `portal`'s event loop."""
        self.portal = portal
        self.session = session

    def tool(self, name: str, **arguments: object) -> CallToolResult:
        """Call a tool, and return its result."""
        return self.portal.call(self.session.call_tool, name, arguments)

    def result(self, name: str, **arguments: object) -> str:
        """Call a tool that succeeds, and return its text."""
        result = self.tool(name, **arguments)
        assert result.is_error is False, result
        [content] = result.content
        assert isinstance(content, TextContent)
        return content.text

    def call(self, name: str, **arguments: object) -> dict[str, Any]:
        """Call a tool that succeeds, and return what it returned."""
        return json.loads(self.result(name, **arguments))

    def refused(self, name: str, **arguments: object) -> str:
        """Call a tool that refuses, and return its code."""
        result = self.tool(name, **arguments)
        assert result.is_error is True, result
        [content] = result.content
        assert isinstance(content, TextContent)
        refusal = json.loads(content.text)
        assert refusal["message"]
        return refusal["code"]

    def feed(self, **arguments: object) -> list[dict[str, Any]]:
        """Read a page of the feed, its end line last."""
        return [json.loads(line) for line in self.result("comment_feed", **arguments).splitlines()]

    def publish(self, content: str = REPORT, **arguments: object) -> dict[str, Any]:
        """Publish the report, or `content`."""
        return self.call(
            "artifact_publish",
            title="Cache report",
            content_type="text/html",
            content=content,
            **arguments,
        )


@contextmanager
def connected(store: Store) -> Iterator[Client]:
    """Connect a client to the MCP server, whose every call reaches `store`.

    Yields:
        The client, connected until the block ends.
    """

    @contextmanager
    def open_store(_ctx: object) -> Iterator[Store]:
        yield store

    with (
        start_blocking_portal() as portal,
        portal.wrap_async_context_manager(mcp.Client(server.server(open_store))) as session,
    ):
        yield Client(portal, session)


@pytest.fixture
def client(agent: MakeAgent) -> Iterator[Client]:
    """A client as an agent of Sam's, in canopy/sam."""
    with connected(agent()) as found:
        yield found


def test_a_published_artifact_reads_back_with_its_visible_text(client: Client) -> None:
    made = client.publish(origin={"canopy.ticket": "PROJ-1"})

    read = client.call("artifact_read", artifact_id=made["artifact_id"])

    assert made["url"] == f"https://louvre.test/a/{made['artifact_id']}?v=1"
    assert read["content"] == REPORT
    assert read["text"] == (
        "Cache report The cache is slow under load, because every miss takes the lock. We should shard it."
    )
    assert read["artifact"]["origin"] == {"canopy.ticket": "PROJ-1"}


def test_a_thread_follows_its_words_into_a_new_version_or_reads_passage_gone(client: Client) -> None:
    artifact = client.publish()["artifact_id"]
    kept = client.call(
        "comment_create",
        artifact_id=artifact,
        anchor={"exact": "every miss takes the lock", "prefix": "under load, because "},
        body="Which lock?",
    )["thread_id"]
    gone = client.call("comment_create", artifact_id=artifact, anchor={"exact": "We should shard it."}, body="How?")[
        "thread_id"
    ]
    client.publish(REVISED, artifact_id=artifact)

    threads = {t["id"]: t for t in client.call("thread_list", artifact_id=artifact)["threads"]}

    assert threads[kept]["anchor_status"] == "found"
    assert threads[gone]["anchor_status"] == "passage_gone"
    assert client.refused("comment_create", artifact_id=artifact, anchor={"exact": "shard it"}, body="x") == (
        "anchor_not_found"
    )


def test_the_feed_carries_each_change_and_ends_with_its_cursor(client: Client) -> None:
    artifact = client.publish()["artifact_id"]
    thread = client.call("comment_create", artifact_id=artifact, body="Overall?")["thread_id"]
    client.call("comment_reply", thread_id=thread, body="Fine.")
    client.call("thread_resolve", thread_id=thread, resolved=True)

    page = client.feed()

    assert [c["kind"] for c in page] == ["comment_created", "comment_created", "thread_resolved", "end"]
    assert page[-1] == {"kind": "end", "through": 3}
    assert client.feed(since=3) == [{"kind": "end", "through": 3}]


def test_another_namespace_is_out_of_scope(client: Client, agent: MakeAgent) -> None:
    artifact = client.publish()["artifact_id"]

    with connected(agent("canopy/other")) as other:
        assert other.refused("artifact_read", artifact_id=artifact) == "out_of_scope"
        assert other.call("artifact_list") == {"artifacts": [], "next_cursor": None}


def test_a_read_only_token_refuses_every_write(client: Client, agent: MakeAgent) -> None:
    artifact = client.publish()["artifact_id"]
    thread = client.call("comment_create", artifact_id=artifact, body="x")["thread_id"]

    with connected(agent(scopes=("read",))) as reader:
        assert reader.refused("artifact_publish", title="t", content_type="text/markdown", content="x") == "read_only"
        assert reader.refused("comment_create", artifact_id=artifact, body="x") == "read_only"
        assert reader.refused("comment_reply", thread_id=thread, body="x") == "read_only"
        assert reader.refused("thread_resolve", thread_id=thread, resolved=True) == "read_only"
        assert reader.call("artifact_read", artifact_id=artifact)["content"] == REPORT


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("artifact_read", {"artifact_id": "a_missing"}),
        ("thread_list", {"artifact_id": "a_missing"}),
        ("comment_create", {"artifact_id": "a_missing", "body": "x"}),
        ("comment_reply", {"thread_id": "t_missing", "body": "x"}),
        ("thread_resolve", {"thread_id": "t_missing", "resolved": True}),
        ("decision_read", {"decision_id": "d_missing"}),
        ("decision_close", {"decision_id": "d_missing"}),
        ("decision_list", {"artifact_id": "a_missing"}),
        ("decision_create", {"artifact_id": "a_missing", "question": "q", "options": [{"label": "a"}, {"label": "b"}]}),
        ("artifact_publish", {"title": "t", "content_type": "text/html", "content": "x", "artifact_id": "a_missing"}),
    ],
)
def test_an_id_the_store_does_not_have_is_not_found(client: Client, name: str, arguments: dict[str, object]) -> None:
    assert client.refused(name, **arguments) == "not_found"


def test_what_is_over_its_bound_is_too_long(client: Client) -> None:
    artifact = client.publish()["artifact_id"]

    assert client.refused("comment_create", artifact_id=artifact, body="x" * (MAX_BODY + 1)) == "too_long"
    assert client.refused(
        "comment_create",
        artifact_id=artifact,
        anchor={"exact": "shard", "prefix": "p" * 33},
        body="x",
    ) == ("too_long")
    pairs = {f"k{i}": "v" for i in range(MAX_ORIGIN + 1)}
    assert client.refused("artifact_publish", title="t", content_type="text/html", content="x", origin=pairs) == (
        "too_long"
    )


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("artifact_publish", {"title": "t", "content_type": "text/plain", "content": "x"}),
        ("artifact_publish", {"title": " ", "content_type": "text/html", "content": "x"}),
        ("artifact_publish", {"title": "t", "content_type": "text/html"}),
        ("artifact_read", {"artifact_id": 7}),
        ("artifact_list", {"cursor": "next"}),
        ("comment_feed", {"limit": MAX_FEED + 1}),
        ("comment_feed", {"since": 2**64}),
        ("thread_resolve", {"thread_id": "t_1", "resolved": "yes"}),
        ("comment_reply", {"thread_id": "t_1", "body": "  \n"}),
        ("decision_create", {"artifact_id": "a_1", "question": "q", "options": [{"label": "a", "colour": "red"}]}),
        ("decision_feed", {"limit": 0}),
        ("decision_list", {"state": "decided"}),
    ],
)
def test_arguments_the_tool_cannot_use_are_invalid(client: Client, name: str, arguments: dict[str, object]) -> None:
    assert client.refused(name, **arguments) == "invalid"


def test_style_get_hands_over_the_house_style(client: Client) -> None:
    assert client.call("style_get") == {
        "version": style.VERSION,
        "css": style.CSS,
        "rules": style.RULES,
        "kind": "report",
        "starter": style.STARTERS[style.Kind.REPORT],
        "kinds": dict(style.KINDS),
    }


def test_style_get_hands_over_the_starter_page_of_the_kind_asked_for(client: Client) -> None:
    given = client.call("style_get", kind="decision")

    assert given["kind"] == "decision"
    assert given["starter"] == style.STARTERS[style.Kind.DECISION]
    assert client.refused("style_get", kind="essay") == "invalid"


def test_style_check_finds_what_a_page_should_change(client: Client) -> None:
    starter = client.call("style_check", content=style.STARTERS[style.Kind.REPORT])
    page = client.call("style_check", content=REPORT)

    assert starter["ok"] is False
    assert {f["rule"] for f in starter["findings"]} == {"placeholder"}
    assert page["ok"] is True
    assert {f["severity"] for f in page["findings"]} == {"warning"}
    assert client.refused("style_check") == "invalid"


def test_style_chart_draws_a_figure_from_data(client: Client) -> None:
    drawn = client.call(
        "style_chart",
        kind="bar",
        finding="Redis makes the fewest tax calls",
        measure="Tax calls a week",
        labels=["Process", "Redis"],
        series=[{"name": "calls", "values": [1_200_000, 190_000]}],
        focus="Redis",
        notes=[{"label": "Redis", "text": "Recommended."}],
    )

    assert drawn["figure"].startswith('<figure class="l-plot">\n<figcaption><span class="l-say">Redis makes the fewest')
    assert "<li>Recommended.</li>" in drawn["figure"]
    assert client.refused("style_chart", kind="line", finding="f", measure="m", labels=["a"], series=[]) == "invalid"
    assert client.refused("style_chart", kind="pie", finding="f", measure="m", labels=["a"], series=[]) == "invalid"


def test_files_publish_publishes_a_page_with_its_files_beside_it(client: Client) -> None:
    csv = base64.b64encode(b"region,p95\nus-east,410\n").decode()
    page = '<h1>p95</h1><a href="p95.csv">The data</a>'

    made = client.call(
        "files_publish",
        title="p95",
        content_type="text/html",
        content=page,
        files=[{"path": "p95.csv", "content_type": "text/csv", "data": csv}],
    )
    bad = client.refused(
        "files_publish",
        title="p95",
        content_type="text/html",
        content=page,
        files=[{"path": "p95.csv", "content_type": "text/csv", "data": "not base64!"}],
    )
    wrong = client.refused(
        "files_publish",
        title="p95",
        content_type="text/html",
        content=page,
        files=[{"path": "p95.png", "content_type": "image/png", "data": csv}],
    )

    assert made["version"] == 1
    assert client.call("artifact_read", artifact_id=made["artifact_id"])["content"] == page
    assert bad == "invalid"
    assert wrong == "invalid"


def test_board_publish_puts_artifacts_side_by_side_and_publishes_the_board_again(client: Client) -> None:
    page = client.publish()["artifact_id"]
    phone = {"artifact_id": page, "label": "Phone, 390", "width": 390, "height": 844}
    laptop = {"artifact_id": page, "label": "Laptop, 1440", "width": 1440, "height": 900}

    made = client.call("board_publish", title="Cache report, two screens", rows=[[laptop, phone]])
    again = client.call("board_publish", title="Cache report, a phone", rows=[[phone]], board_id=made["board_id"])

    assert made == {"board_id": made["board_id"], "frames": 2, "url": f"https://louvre.test/b/{made['board_id']}"}
    assert again["board_id"] == made["board_id"]
    assert client.refused("board_publish", title="Nothing", rows=[]) == "invalid"
    assert client.refused("board_publish", title="Tiny", rows=[[{**phone, "width": 10}]]) == "invalid"
    assert client.refused("board_publish", title="Gone", rows=[[{**phone, "artifact_id": "a_nowhere"}]]) == "not_found"


def test_map_publish_publishes_geojson_that_louvre_draws_and_refuses_what_is_not(client: Client) -> None:
    pole = {"type": "Feature", "properties": {"name": "P-103", "status": "lamp out"}, "geometry": None}
    data = {
        "type": "FeatureCollection",
        "features": [{**pole, "geometry": {"type": "Point", "coordinates": [-9.1, 38.7]}}],
    }

    made = client.call("map_publish", title="One lamp is out", data=data)
    read = client.call("artifact_read", artifact_id=made["artifact_id"])
    off = {**data, "features": [{**pole, "geometry": {"type": "Point", "coordinates": [38.7, -91]}}]}

    assert read["version"]["content_type"] == "application/geo+json"
    assert json.loads(read["content"]) == data
    assert "P-103 status lamp out" in read["text"]
    assert client.refused("map_publish", title="Off the earth", data=off) == "invalid"
    assert client.refused("map_publish", title="Not GeoJSON", data={"type": "Topology"}) == "invalid"
    assert client.refused("artifact_publish", title="t", content_type="application/geo+json", content="{}") == "invalid"


def test_style_check_holds_a_page_to_the_files_published_beside_it(client: Client) -> None:
    page = '<h1>p95</h1><img src="p95.png" alt="p95">'

    beside = client.call("style_check", content=page, files=["p95.png", "unused.csv"])
    alone = client.call("style_check", content=page)

    assert {(f["rule"], f["severity"]) for f in beside["findings"]} >= {("file", "warning")}
    assert beside["ok"] is True
    assert alone["ok"] is False
    assert ("file", "error") in {(f["rule"], f["severity"]) for f in alone["findings"]}


def test_the_style_is_resources_each_naming_its_version(client: Client) -> None:
    listed = client.portal.call(client.session.list_resources).resources
    read = {r.uri: client.portal.call(client.session.read_resource, r.uri).contents for r in listed}

    assert [(r.uri, r.mime_type) for r in listed] == [
        ("louvre://style/louvre-1/style.css", "text/css"),
        ("louvre://style/louvre-1/rules.md", "text/markdown"),
        ("louvre://style/louvre-1/starters/report.html", "text/html"),
        ("louvre://style/louvre-1/starters/decision.html", "text/html"),
        ("louvre://style/louvre-1/starters/plan.html", "text/html"),
        ("louvre://style/louvre-1/starters/map.html", "text/html"),
    ]
    assert [[c.text for c in contents if isinstance(c, TextResourceContents)] for contents in read.values()] == [
        [style.CSS],
        [style.RULES],
        *([starter] for starter in style.STARTERS.values()),
    ]
    with pytest.raises(MCPError):
        client.portal.call(client.session.read_resource, "louvre://style/louvre-0/style.css")


def test_the_style_prompt_asks_for_a_page_about_what_it_is_given(client: Client) -> None:
    [listed] = client.portal.call(client.session.list_prompts).prompts
    given = client.portal.call(client.session.get_prompt, "style", {"about": "checkout latency"})
    bare = client.portal.call(client.session.get_prompt, "style", None)
    [message] = given.messages
    assert isinstance(message.content, TextContent)
    [plain] = bare.messages
    assert isinstance(plain.content, TextContent)

    assert listed.name == "style"
    assert message.role == "user"
    assert [a.name for a in listed.arguments or []] == ["about", "kind"]
    assert message.content.text.startswith("Write a report about checkout latency as an HTML artifact")
    assert "style_check" in message.content.text
    assert style.RULES in message.content.text
    assert style.STARTERS[style.Kind.REPORT] in message.content.text
    assert plain.content.text.startswith("Write the report I ask for as an HTML artifact")
    with pytest.raises(MCPError):
        client.portal.call(client.session.get_prompt, "publish", None)


def test_the_style_prompt_starts_from_the_kind_it_is_given(client: Client) -> None:
    given = client.portal.call(client.session.get_prompt, "style", {"about": "the queue", "kind": "plan"})
    [message] = given.messages
    assert isinstance(message.content, TextContent)

    assert message.content.text.startswith("Write a plan about the queue as an HTML artifact")
    assert style.STARTERS[style.Kind.PLAN] in message.content.text
    with pytest.raises(MCPError):
        client.portal.call(client.session.get_prompt, "style", {"kind": "essay"})


def test_it_serves_its_tools_and_says_what_it_is_for(client: Client) -> None:
    tools = client.portal.call(client.session.list_tools).tools
    info = client.session.server_info

    assert [t.name for t in tools] == TOOLS
    assert "$ref" not in json.dumps([t.input_schema for t in tools])
    assert info is not None
    assert info.name == "louvre"
    assert client.session.instructions == server.INSTRUCTIONS
    with pytest.raises(MCPError):
        client.tool("artifact_delete")


def test_an_agent_asks_a_decision_and_reads_back_what_people_chose(client: Client, conn: Connection) -> None:
    artifact = client.publish()["artifact_id"]
    asked = client.call(
        "decision_create",
        artifact_id=artifact,
        question="Shard the cache, or not yet?",
        options=[
            {"label": "Shard it", "detail": "A week's work.", "anchor": {"exact": "We should shard it."}},
            {"label": "Not yet"},
        ],
        asked=["ana"],
    )
    ana = Decisions(Store(conn, accounts.person_scope(person(conn, "ana", "Ana Ruiz"))))
    ana.answer(asked["decision_id"], ["o1"], "Before the sale.")

    read = client.call("decision_read", decision_id=asked["decision_id"])
    listed = client.call("decision_list", artifact_id=artifact, state="open")
    events = [json.loads(line) for line in client.result("decision_feed").splitlines()]
    closed = client.call("decision_close", decision_id=asked["decision_id"], outcome="o1", note="Sharding next sprint.")

    assert [(o["id"], o["label"], o["count"]) for o in read["options"]] == [("o1", "Shard it", 1), ("o2", "Not yet", 0)]
    assert read["options"][0]["anchor"] == {"exact": "We should shard it.", "prefix": "", "suffix": ""}
    assert read["answers"] == [
        {
            "account_id": "dev:ana",
            "name": "Ana Ruiz",
            "choices": ["o1"],
            "note": "Before the sale.",
            "answered_at": read["answers"][0]["answered_at"],
        },
    ]
    assert read["asked"] == [{"login": "ana", "name": "Ana Ruiz", "answered": True}]
    assert [d["id"] for d in listed["decisions"]] == [asked["decision_id"]]
    assert [(e["kind"], e.get("choices")) for e in events] == [
        ("decision_asked", []),
        ("decision_answered", ["o1"]),
        ("end", None),
    ]
    assert closed["state"] == "closed"
    assert client.refused("decision_close", decision_id=asked["decision_id"]) == "closed"


def test_a_decisions_options_may_be_places_on_a_map_an_agent_published(client: Client) -> None:
    poles = [
        {"type": "Feature", "properties": {"name": n}, "geometry": {"type": "Point", "coordinates": [-9.1, 38.7]}}
        for n in ("P-104", "P-113")
    ]
    made = client.call("map_publish", title="Poles", data={"type": "FeatureCollection", "features": poles})
    options = [
        {"label": "The lamp", "place": {"kind": "feature", "id": "P-104"}},
        {"label": "The corner", "place": {"kind": "point", "coordinates": [-9.1, 38.71]}},
    ]

    asked = client.call("decision_create", artifact_id=made["artifact_id"], question="Which first?", options=options)
    read = client.call("decision_read", decision_id=asked["decision_id"])
    missing = [{"label": "Gone", "place": {"kind": "feature", "id": "P-999"}}, {"label": "Neither"}]

    assert [o["place"]["kind"] for o in read["options"]] == ["feature", "point"]
    assert [o["anchor"]["exact"] for o in read["options"]] == ["P-104", "38.71000° N, 9.10000° W"]
    assert client.refused(
        "decision_create",
        artifact_id=made["artifact_id"],
        question="?",
        options=missing,
    ) == ("anchor_not_found")


def test_a_decision_is_never_answered_with_a_token(client: Client, agent: MakeAgent) -> None:
    artifact = client.publish()["artifact_id"]
    options = [{"label": "Yes"}, {"label": "No"}]
    tools = client.portal.call(client.session.list_tools).tools

    assert "decision_answer" not in [t.name for t in tools]
    assert client.refused("decision_create", artifact_id=artifact, question="Ship?", options=options[:1]) == "invalid"
    made = client.call("decision_create", artifact_id=artifact, question="Ship?", options=options)
    with connected(agent(scopes=("read",))) as reader:
        assert reader.refused("decision_create", artifact_id=artifact, question="Ship?", options=options) == "read_only"
        assert reader.refused("decision_close", decision_id=made["decision_id"]) == "read_only"
