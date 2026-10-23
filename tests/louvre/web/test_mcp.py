"""The MCP server over streamable HTTP: a token in, JSON-RPC answered as JSON."""

import json

from fastapi.testclient import TestClient

from louvre.core import accounts
from louvre.core.db import Connection
from tests.conftest import MakeWeb, person, sign_in


def mint(conn: Connection, scopes: set[str] | None = None) -> str:
    """Mint a token of Sam's in canopy/sam, and return its secret."""
    sam = person(conn, "sam", "Sam Okafor")
    _, secret = accounts.mint(conn, sam, "canopy worker", "canopy/sam", scopes or {"read", "publish", "comment"})
    return secret


def rpc(client: TestClient, secret: str, method: str, params: dict[str, object] | None = None) -> dict[str, object]:
    """Send one request, and return its response."""
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        headers={"Authorization": f"Bearer {secret}", "Accept": "application/json, text/event-stream"},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    return response.json()


def test_an_agent_publishes_and_a_person_reads_it_on_the_web(web: MakeWeb, conn: Connection) -> None:
    agent, ana = web(), web()
    secret = mint(conn)

    hello = rpc(agent, secret, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})
    called = rpc(
        agent,
        secret,
        "tools/call",
        {"name": "artifact_publish", "arguments": {"title": "R", "content_type": "text/markdown", "content": "# R"}},
    )
    made = json.loads(called["result"]["content"][0]["text"])  # type: ignore[index]
    sign_in(ana, "ana")

    assert hello["result"]["protocolVersion"] == "2025-06-18"  # type: ignore[index]
    assert made["url"] == f"https://louvre.test/a/{made['artifact_id']}?v=1"
    assert ana.get(f"/api/artifacts/{made['artifact_id']}").json()["owned"] is False
    assert ana.get(f"/api/artifacts/{made['artifact_id']}").json()["artifact"]["namespace"] == "canopy/sam"


def test_an_agents_comment_says_so_and_whose_agent_it_is(web: MakeWeb, conn: Connection) -> None:
    client = web()
    secret = mint(conn)
    made = rpc(
        client,
        secret,
        "tools/call",
        {"name": "artifact_publish", "arguments": {"title": "R", "content_type": "text/html", "content": "<p>Hi</p>"}},
    )
    artifact = json.loads(made["result"]["content"][0]["text"])["artifact_id"]  # type: ignore[index]
    rpc(
        client,
        secret,
        "tools/call",
        {"name": "comment_create", "arguments": {"artifact_id": artifact, "body": "Done."}},
    )
    sign_in(client, "ana")

    [thread] = client.get(f"/api/artifacts/{artifact}/threads").json()["threads"]

    assert thread["comments"][0]["author"] == {
        "id": "agent:dev:sam:canopy worker",
        "display_name": "canopy worker",
        "kind": "agent",
        "on_behalf_of": "dev:sam",
    }
    assert thread["comments"][0]["via"] == "mcp"


def test_a_call_without_a_working_token_is_unauthorized(web: MakeWeb, conn: Connection) -> None:
    client = web()
    secret = mint(conn)
    accounts.revoke(conn, person(conn, "sam"), accounts.tokens(conn, person(conn, "sam"))[0].id)
    body = {"jsonrpc": "2.0", "id": 1, "method": "ping"}

    tried: list[dict[str, str]] = [{}, {"Authorization": "Bearer lvt_nope"}, {"Authorization": f"Bearer {secret}"}]
    for headers in tried:
        response = client.post("/mcp", json=body, headers=headers)

        assert response.status_code == 401
        assert response.headers["www-authenticate"].startswith("Bearer")


def test_a_notification_is_accepted_and_never_answered(web: MakeWeb, conn: Connection) -> None:
    response = web().post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers={"Authorization": f"Bearer {mint(conn)}"},
    )

    assert response.status_code == 202
    assert response.content == b""


def test_there_is_no_stream_to_open(web: MakeWeb) -> None:
    assert web().get("/mcp").status_code == 405


def test_a_cookie_is_no_token(web: MakeWeb) -> None:
    client = web()
    sign_in(client, "ana")

    assert client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"}).status_code == 401
