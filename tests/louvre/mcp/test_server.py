"""The MCP server answers the contract's tools, and style_get, as canopy's local store does, to the SDK's client."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import mcp
import pytest
from anyio.from_thread import BlockingPortal, start_blocking_portal
from mcp.shared.exceptions import MCPError
from mcp.types import CallToolResult, TextContent, TextResourceContents

from louvre.core import style
from louvre.core.store import MAX_BODY, MAX_FEED, MAX_ORIGIN, Store
from louvre.mcp import server
from tests.conftest import MakeAgent

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
    ],
)
def test_arguments_the_tool_cannot_use_are_invalid(client: Client, name: str, arguments: dict[str, object]) -> None:
    assert client.refused(name, **arguments) == "invalid"


def test_style_get_hands_over_the_house_style(client: Client) -> None:
    assert client.call("style_get") == {
        "version": style.VERSION,
        "css": style.CSS,
        "rules": style.RULES,
        "starter": style.STARTER,
    }


def test_the_style_is_resources_each_naming_its_version(client: Client) -> None:
    listed = client.portal.call(client.session.list_resources).resources
    read = {r.uri: client.portal.call(client.session.read_resource, r.uri).contents for r in listed}

    assert [(r.uri, r.mime_type) for r in listed] == [
        ("louvre://style/louvre-1/style.css", "text/css"),
        ("louvre://style/louvre-1/rules.md", "text/markdown"),
        ("louvre://style/louvre-1/starter.html", "text/html"),
    ]
    assert [[c.text for c in contents if isinstance(c, TextResourceContents)] for contents in read.values()] == [
        [style.CSS],
        [style.RULES],
        [style.STARTER],
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
    assert message.content.text.startswith("Write a page about checkout latency as an HTML artifact")
    assert style.RULES in message.content.text
    assert style.STARTER in message.content.text
    assert plain.content.text.startswith("Write the page I ask for as an HTML artifact")
    with pytest.raises(MCPError):
        client.portal.call(client.session.get_prompt, "publish", None)


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
