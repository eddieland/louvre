"""The MCP server answers the artifacts contract's tools, and style_get, as canopy's local store does."""

import itertools
import json
from collections.abc import Mapping
from typing import Any

import pytest

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
    """Calls a store's tools through the MCP server, one JSON-RPC message at a time."""

    def __init__(self, store: Store) -> None:
        """Call `store`."""
        self.store = store
        self._ids = itertools.count(1)

    def request(self, method: str, params: Mapping[str, object] | None = None) -> dict[str, Any]:
        """Send a request, and return its response."""
        line = json.dumps({"jsonrpc": "2.0", "id": next(self._ids), "method": method, "params": params or {}})
        response = server.answer(line.encode(), self.store)
        assert response is not None
        return response

    def result(self, name: str, **arguments: object) -> str:
        """Call a tool, and return its result."""
        result = self.request("tools/call", {"name": name, "arguments": arguments})["result"]
        assert result["isError"] is False, result
        [content] = result["content"]
        return str(content["text"])

    def call(self, name: str, **arguments: object) -> dict[str, Any]:
        """Call a tool that succeeds, and return what it returned."""
        return json.loads(self.result(name, **arguments))

    def refused(self, name: str, **arguments: object) -> str:
        """Call a tool that refuses, and return its code."""
        result = self.request("tools/call", {"name": name, "arguments": arguments})["result"]
        assert result["isError"] is True, result
        refusal = json.loads(result["content"][0]["text"])
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


@pytest.fixture
def client(agent: MakeAgent) -> Client:
    """A client as an agent of Sam's, in canopy/sam."""
    return Client(agent())


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
    other = Client(agent("canopy/other"))

    assert other.refused("artifact_read", artifact_id=artifact) == "out_of_scope"
    assert other.call("artifact_list") == {"artifacts": [], "next_cursor": None}


def test_a_read_only_token_refuses_every_write(client: Client, agent: MakeAgent) -> None:
    artifact = client.publish()["artifact_id"]
    thread = client.call("comment_create", artifact_id=artifact, body="x")["thread_id"]
    reader = Client(agent(scopes=("read",)))

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
    assert client.call("style_get") == {"version": style.VERSION, "css": style.CSS, "rules": style.RULES}


def test_it_serves_its_tools_and_nothing_else(client: Client) -> None:
    hello = client.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}})["result"]
    assert hello["protocolVersion"] == "2024-11-05"
    assert hello["serverInfo"]["name"] == "louvre"
    assert (
        client.request("initialize", {"protocolVersion": "1999-01-01"})["result"]["protocolVersion"]
        == (server.PROTOCOL_VERSIONS[0])
    )
    tools = client.request("tools/list")["result"]["tools"]
    assert [t["name"] for t in tools] == TOOLS
    assert "$ref" not in json.dumps([t["inputSchema"] for t in tools])
    assert client.request("ping")["result"] == {}
    assert client.request("resources/list")["error"]["code"] == server.METHOD_NOT_FOUND
    assert client.request("tools/call", {"name": "artifact_delete", "arguments": {}})["error"]["code"] == (
        server.INVALID_PARAMS
    )
    assert server.answer(b"{not json", client.store) == {
        "jsonrpc": "2.0",
        "id": None,
        "error": {"code": server.PARSE_ERROR, "message": "not a JSON message"},
    }
    assert server.answer(b"[]", client.store)["error"]["code"] == server.INVALID_REQUEST  # type: ignore[index]
    assert server.answer(b'{"jsonrpc": "2.0", "method": "notifications/initialized"}', client.store) is None
