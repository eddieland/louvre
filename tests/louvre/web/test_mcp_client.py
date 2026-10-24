"""An agent's runtime reaching Louvre: the official MCP client, over streamable HTTP, doing what canopy's skill says.

The server's other tests call it in process, or send JSON-RPC by hand; these hold Louvre over HTTP to a client agents
run, so a skill written against canopy's local store (`.agents/skills/canopy-artifacts` in canopy) works against
Louvre unchanged (M5). Tokens are minted on the web and the person comments there, as on a deployment.
"""

import asyncio
import json
from collections.abc import Callable, Coroutine, Iterator
from contextlib import contextmanager

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent

from tests.conftest import WRITES

#: Every scope a token may carry.
ALL_SCOPES = ("read", "publish", "comment")
#: What the worker publishes first, and the passage the person comments on.
REPORT = "# Checkout latency\n\nThe p99 rose to 840 ms after the cache change.\n"
#: The worker's revision, which answers the comment and keeps its passage.
REVISED = "# Checkout latency\n\nThe p99 rose to 840 ms after the cache change in PR 42.\n"

#: What an agent does once connected: its calls, and what it found.
type Steps[T] = Callable[[ClientSession], Coroutine[None, None, T]]


@contextmanager
def signed_in(live_app: str, login: str) -> Iterator[httpx2.Client]:
    """Sign in on the web as `login`, by name.

    Yields:
        A client of the live app, with the session's cookie.
    """
    with httpx2.Client(base_url=live_app, headers=WRITES) as web:
        response = web.post("/auth/dev", json={"login": login})
        assert response.status_code == 204, response.text
        yield web


def mint(web: httpx2.Client, scopes: tuple[str, ...] = ALL_SCOPES) -> str:
    """Mint a token on the Tokens page's API, in canopy/ana.

    Returns:
        Its secret.
    """
    response = web.post("/api/tokens", json={"name": "canopy worker", "namespace": "canopy/ana", "scopes": scopes})
    assert response.status_code == 201, response.text
    return str(response.json()["secret"])


def run_agent[T](live_app: str, secret: str, steps: Steps[T]) -> T:
    """Connect to `/mcp` with the token `secret`, as a runtime does, and take `steps`.

    Returns:
        What the steps found.
    """

    async def connected() -> T:
        headers = {"Authorization": f"Bearer {secret}"}
        async with (
            httpx2.AsyncClient(headers=headers) as http,
            streamable_http_client(f"{live_app}/mcp", http_client=http) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            return await steps(session)

    return asyncio.run(connected())


async def call(session: ClientSession, name: str, arguments: dict[str, object]) -> dict[str, object]:
    """Call a tool that should answer.

    Returns:
        Its answer.
    """
    error, text = await attempt(session, name, arguments)
    assert not error, text
    return json.loads(text)


async def attempt(session: ClientSession, name: str, arguments: dict[str, object]) -> tuple[bool, str]:
    """Call a tool that may be refused.

    Returns:
        Whether it was refused, and the text it answered.
    """
    result = await session.call_tool(name, arguments)
    assert isinstance(result, CallToolResult)
    first = result.content[0]
    assert isinstance(first, TextContent)
    return result.is_error, first.text


def test_an_agent_publishes_reads_a_persons_comment_and_replies_in_its_thread(live_app: str) -> None:
    with signed_in(live_app, "ana") as ana:
        secret = mint(ana)

        async def publish(session: ClientSession) -> tuple[list[str], dict[str, object]]:
            tools = await session.list_tools()
            published = await call(
                session,
                "artifact_publish",
                {
                    "title": "Checkout latency",
                    "content_type": "text/markdown",
                    "content": REPORT,
                    "origin": {"canopy.ticket": "PROJ-1"},
                },
            )
            return [t.name for t in tools.tools], published

        tools, published = run_agent(live_app, secret, publish)
        artifact_id = str(published["artifact_id"])
        anchor = {"exact": "rose to 840 ms", "prefix": "The p99 ", "suffix": " after"}
        commented = ana.post(f"/api/artifacts/{artifact_id}/threads", json={"anchor": anchor, "body": "Which change?"})
        assert commented.status_code == 201, commented.text

        async def answer(session: ClientSession) -> tuple[dict[str, object], dict[str, object]]:
            listed = await call(session, "artifact_list", {"origin": {"canopy.ticket": "PROJ-1"}})
            threads = await call(session, "thread_list", {"artifact_id": artifact_id})
            [thread] = threads["threads"]  # type: ignore[misc]
            await call(
                session,
                "artifact_publish",
                {
                    "artifact_id": artifact_id,
                    "title": "Checkout latency",
                    "content_type": "text/markdown",
                    "content": REVISED,
                },
            )
            await call(session, "comment_reply", {"thread_id": thread["id"], "body": "PR 42; version 2 names it."})
            await call(session, "thread_resolve", {"thread_id": thread["id"], "resolved": True})
            return listed, thread

        listed, seen = run_agent(live_app, secret, answer)
        [on_the_web] = ana.get(f"/api/artifacts/{artifact_id}/threads").json()["threads"]

    assert "artifact_publish" in tools
    assert "comment_feed" in tools
    assert published["version"] == 1
    assert [a["id"] for a in listed["artifacts"]] == [artifact_id]  # type: ignore[union-attr]
    assert [c["body"] for c in seen["comments"]] == ["Which change?"]  # type: ignore[union-attr]
    assert on_the_web["state"] == "resolved"
    assert on_the_web["anchor_status"] == "found"
    assert [(c["author"]["kind"], c["author"]["on_behalf_of_name"], c["via"]) for c in on_the_web["comments"]] == [
        ("person", None, "web"),
        ("agent", "Ana", "mcp"),
    ]


def test_a_read_tokens_writes_are_refused_read_only(live_app: str) -> None:
    with signed_in(live_app, "ana") as ana:
        writer, reader = mint(ana), mint(ana, ("read",))

    async def publish(session: ClientSession) -> tuple[str, str]:
        made = await call(session, "artifact_publish", {"title": "R", "content_type": "text/markdown", "content": "R"})
        thread = await call(session, "comment_create", {"artifact_id": made["artifact_id"], "body": "First."})
        return str(made["artifact_id"]), str(thread["thread_id"])

    artifact_id, thread_id = run_agent(live_app, writer, publish)

    async def write(session: ClientSession) -> list[tuple[bool, str]]:
        return [
            await attempt(session, "artifact_publish", {"title": "R", "content_type": "text/markdown", "content": "R"}),
            await attempt(session, "comment_reply", {"thread_id": thread_id, "body": "No."}),
            await attempt(session, "thread_resolve", {"thread_id": thread_id, "resolved": True}),
            await attempt(session, "thread_list", {"artifact_id": artifact_id}),
        ]

    *writes, read = run_agent(live_app, reader, write)

    assert [(error, json.loads(text)["code"]) for error, text in writes] == [(True, "read_only")] * 3
    assert read[0] is False
    assert [c["body"] for t in json.loads(read[1])["threads"] for c in t["comments"]] == ["First."]
