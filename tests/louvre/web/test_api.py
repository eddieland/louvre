"""The web UI's API: what a person reads and writes, held to who they are."""

from unittest import mock

import pytest

from louvre.core import accounts
from louvre.core.db import Connection
from louvre.core.decisions import Decisions, Option
from louvre.core.text import Anchor
from louvre.web import ui
from louvre.web.app import ARTIFACT_POLICY
from tests.conftest import WRITES, MakeAgent, MakeWeb, sign_in

#: A report, and the passage a thread is on.
REPORT = "<h1>Report</h1><p>We will retry the fraud check twice before declining.</p>"


@pytest.fixture
def published(agent: MakeAgent) -> str:
    """An artifact Sam's agent published in canopy/sam."""
    return str(agent().publish(title="Report", content_type="text/html", content=REPORT)["artifact_id"])


def test_the_session_says_who_is_signed_in_and_how_to_sign_in(web: MakeWeb) -> None:
    client = web()
    assert client.get("/api/session").json() == {
        "account": None,
        "configured": True,
        "demo": False,
        "sign_in": {"github": True, "dev": True},
    }

    sign_in(client, "ana", "Ana Ruiz")

    assert client.get("/api/session").json()["account"] == {"id": "dev:ana", "login": "ana", "name": "Ana Ruiz"}


def test_without_a_database_the_session_says_so_and_the_rest_is_unavailable(web: MakeWeb) -> None:
    client = web(database_url=None)

    assert client.get("/api/session").json()["configured"] is False
    response = client.get("/api/artifacts")
    assert response.status_code == 503
    assert response.json()["code"] == "not_configured"


def test_reading_needs_a_sign_in_when_the_demo_is_off(web: MakeWeb, published: str) -> None:
    client = web()

    assert client.get("/api/artifacts").status_code == 401
    assert client.get(f"/api/artifacts/{published}").json()["code"] == "unauthenticated"
    assert client.get(f"/content/{published}/1").status_code == 401


def test_a_signed_in_person_reads_every_namespace(web: MakeWeb, published: str) -> None:
    client = web()
    sign_in(client, "ana")

    listed = client.get("/api/artifacts").json()["artifacts"]
    detail = client.get(f"/api/artifacts/{published}").json()

    assert [a["id"] for a in listed] == [published]
    assert listed[0]["open_threads"] == 0
    assert detail["artifact"]["namespace"] == "canopy/sam"
    assert [v["n"] for v in detail["versions"]] == [1]
    assert detail["owned"] is False


def test_a_thread_is_started_replied_to_resolved_and_edited(web: MakeWeb, published: str) -> None:
    client = web()
    sign_in(client, "ana", "Ana Ruiz")

    made = client.post(
        f"/api/artifacts/{published}/threads",
        json={"anchor": {"exact": "retry the fraud check twice", "prefix": "We will "}, "body": "Why twice?"},
        headers=WRITES,
    )
    thread = made.json()["thread_id"]
    replied = client.post(f"/api/threads/{thread}/replies", json={"body": "And how long?"}, headers=WRITES)
    comment = replied.json()["comment_id"]
    client.patch(f"/api/comments/{comment}", json={"body": "And how long between?"}, headers=WRITES)
    client.post(f"/api/threads/{thread}/resolve", json={"resolved": True}, headers=WRITES)

    [listed] = client.get(f"/api/artifacts/{published}/threads").json()["threads"]
    assert made.status_code == replied.status_code == 201
    assert listed["state"] == "resolved"
    assert listed["anchor_status"] == "found"
    assert [c["body"] for c in listed["comments"]] == ["Why twice?", "And how long between?"]
    assert listed["comments"][0]["author"]["display_name"] == "Ana Ruiz"
    assert listed["comments"][0]["via"] == "web"

    assert client.delete(f"/api/comments/{comment}", headers=WRITES).status_code == 200
    [after] = client.get(f"/api/artifacts/{published}/threads").json()["threads"]
    assert after["comments"][1]["deleted_at"] is not None


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        ({"anchor": {"exact": "three times"}, "body": "?"}, 409, "anchor_not_found"),
        ({"body": "  "}, 422, "invalid"),
        ({"body": "x", "extra": 1}, 422, "invalid"),
        ({"anchor": {"exact": "twice", "prefix": "p" * 33}, "body": "x"}, 422, "invalid"),
    ],
)
def test_a_refused_write_says_why(
    web: MakeWeb,
    published: str,
    body: dict[str, object],
    status: int,
    code: str,
) -> None:
    client = web()
    sign_in(client, "ana")

    response = client.post(f"/api/artifacts/{published}/threads", json=body, headers=WRITES)

    assert response.status_code == status
    assert response.json()["code"] == code
    assert response.json()["message"]


def test_another_persons_comment_is_theirs(web: MakeWeb, published: str) -> None:
    ana, raj = web(), web()
    sign_in(ana, "ana")
    sign_in(raj, "raj")
    made = ana.post(f"/api/artifacts/{published}/threads", json={"body": "Mine."}, headers=WRITES).json()

    response = raj.patch(f"/api/comments/{made['comment_id']}", json={"body": "Not."}, headers=WRITES)

    assert response.status_code == 403
    assert response.json()["code"] == "out_of_scope"


def test_a_write_without_the_header_is_forbidden(web: MakeWeb, published: str) -> None:
    client = web()
    sign_in(client, "ana")

    response = client.post(f"/api/artifacts/{published}/threads", json={"body": "From another site?"})

    assert response.status_code == 403
    assert client.post("/auth/dev", json={"login": "raj"}).status_code == 403


def test_the_demo_is_read_without_signing_in_but_not_written(web: MakeWeb) -> None:
    client = web(demo=True)

    listed = client.get("/api/artifacts").json()["artifacts"]
    artifact = listed[-1]["id"]
    response = client.post(f"/api/artifacts/{artifact}/threads", json={"body": "Hi."}, headers=WRITES)

    assert {a["namespace"] for a in listed} == {"demo"}
    assert len(listed) == 8
    assert response.status_code == 403
    assert response.json()["code"] == "read_only"


def test_the_demos_report_has_a_thread_gone_from_its_second_version(web: MakeWeb) -> None:
    client = web(demo=True)
    report = next(a for a in client.get("/api/artifacts").json()["artifacts"] if a["latest_version"] == 2)["id"]

    threads = client.get(f"/api/artifacts/{report}/threads").json()["threads"]
    first = client.get(f"/api/artifacts/{report}/threads", params={"version": 1}).json()["threads"]

    assert [t["anchor_status"] for t in threads].count("passage_gone") == 1
    assert "passage_gone" not in [t["anchor_status"] for t in first]
    agents = [c["author"] for t in threads for c in t["comments"] if c["author"]["kind"] == "agent"]
    assert agents
    assert {a["on_behalf_of_name"] for a in agents} == {"Sam Okafor"}


def test_the_demos_board_is_listed_and_shown_with_its_frames(web: MakeWeb) -> None:
    client = web(demo=True)

    listed = client.get("/api/boards").json()["boards"]
    shown = client.get("/api/boards/design-study").json()

    assert listed == [
        {
            "id": "design-study",
            "title": "Design study, 2026-10-23",
            "namespace": "demo",
            "frames": 6,
            "open_threads": 2,
        },
    ]
    assert shown["board"]["title"] == "Design study, 2026-10-23"
    assert [f["id"] for f in shown["frames"]][:2] == ["gallery-laptop", "gallery-phone"]
    assert shown["frames"][0]["artifact"]["title"] == "Direction: Gallery"


def test_there_are_no_boards_without_the_demo(web: MakeWeb) -> None:
    client = web()
    sign_in(client, "ana")

    assert client.get("/api/boards").json() == {"boards": []}
    response = client.get("/api/boards/design-study")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_only_its_owner_deletes_an_artifact(web: MakeWeb, published: str) -> None:
    ana, sam = web(), web()
    sign_in(ana, "ana")
    sign_in(sam, "sam", "Sam Okafor")

    assert ana.delete(f"/api/artifacts/{published}", headers=WRITES).status_code == 403
    assert sam.get(f"/api/artifacts/{published}").json()["owned"] is True
    assert sam.delete(f"/api/artifacts/{published}", headers=WRITES).status_code == 200
    assert ana.get(f"/api/artifacts/{published}").status_code == 404


def test_tokens_are_minted_listed_and_revoked(web: MakeWeb, conn: Connection) -> None:
    client = web()
    sign_in(client, "ana")

    minted = client.post(
        "/api/tokens",
        json={"name": "canopy worker", "namespace": "canopy/ana", "scopes": ["read", "publish"]},
        headers=WRITES,
    ).json()
    listed = client.get("/api/tokens").json()["tokens"]
    revoked = client.delete(f"/api/tokens/{minted['token']['id']}", headers=WRITES)

    assert minted["secret"].startswith(accounts.TOKEN_PREFIX)
    assert [t["id"] for t in listed] == [minted["token"]["id"]]
    assert listed[0]["scopes"] == ["publish", "read"]
    assert "secret" not in listed[0]
    assert revoked.status_code == 200
    assert accounts.token_scope(conn, minted["secret"]) is None
    assert client.delete(f"/api/tokens/{minted['token']['id']}", headers=WRITES).status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"name": "agent", "namespace": "Not A Namespace", "scopes": ["read"]},
        {"name": "agent", "namespace": "canopy/ana", "scopes": []},
        {"name": "agent", "namespace": "canopy/ana", "scopes": ["admin"]},
    ],
)
def test_a_token_that_cannot_be_used_is_not_minted(web: MakeWeb, body: dict[str, object]) -> None:
    client = web()
    sign_in(client, "ana")

    response = client.post("/api/tokens", json=body, headers=WRITES)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid"


def test_tokens_need_a_sign_in(web: MakeWeb) -> None:
    assert web().get("/api/tokens").status_code == 401


def test_a_versions_page_is_sandboxed_with_the_bridge_at_its_end(web: MakeWeb, published: str) -> None:
    client = web()
    sign_in(client, "ana")

    with mock.patch.object(ui, "bridge", autospec=True, return_value="window.bridged = '</script>'"):
        response = client.get(f"/content/{published}/1")

    assert response.status_code == 200
    assert response.headers["content-security-policy"] == ARTIFACT_POLICY
    assert "allow-same-origin" not in ARTIFACT_POLICY
    assert response.text.startswith(REPORT)
    assert response.text.endswith("<script>window.bridged = '<\\/script>'</script>\n")
    assert client.get(f"/content/{published}/2").status_code == 404


def test_a_markdown_version_is_shown_in_the_house_style(web: MakeWeb, agent: MakeAgent) -> None:
    made = agent().publish(title="Notes", content_type="text/markdown", content="# Notes\n\n<b>not markup</b>")
    client = web()
    sign_in(client, "ana")

    page = client.get(f"/content/{made['artifact_id']}/1").text

    assert '<body class="louvre">' in page
    assert "&lt;b&gt;not markup&lt;/b&gt;" in page


def test_the_house_style_is_public(web: MakeWeb) -> None:
    client = web()

    assert client.get("/api/style").json()["version"] == "louvre-1"
    assert client.get("/api/style", params={"kind": "plan"}).json()["kind"] == "plan"
    assert client.get("/api/style", params={"kind": "essay"}).status_code == 422


def test_an_unknown_api_route_is_json_not_the_ui(web: MakeWeb) -> None:
    response = web().get("/api/nope")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"


def test_a_person_answers_an_agents_decision_on_the_web(web: MakeWeb, agent: MakeAgent, published: str) -> None:
    asked = Decisions(agent()).ask(
        published,
        "Retry twice, or once?",
        (Option("Twice", anchor=Anchor.of("retry the fraud check twice")), Option("Once")),
        asked=["ana"],
    )
    decision = asked["decision_id"]
    client = web()
    sign_in(client, "ana", "Ana Ruiz")

    [shown] = client.get(f"/api/artifacts/{published}/decisions").json()["decisions"]
    before = client.get("/api/decisions").json()
    unheaded = client.post(f"/api/decisions/{decision}/answer", json={"choices": ["o2"]})
    answered = client.post(
        f"/api/decisions/{decision}/answer",
        json={"choices": ["o2"], "note": "Once."},
        headers=WRITES,
    )
    after = client.get("/api/decisions", params={"state": "open"}).json()
    [listed] = client.get("/api/artifacts").json()["artifacts"]
    refused = client.post(f"/api/decisions/{decision}/close", json={"outcome": "o2"}, headers=WRITES)

    assert shown["question"] == "Retry twice, or once?"
    assert shown["author"]["on_behalf_of_name"] == "Sam Okafor"
    assert (shown["awaits_me"], before["awaiting"]) == (True, 1)
    assert unheaded.status_code == 403
    assert answered.status_code == 200
    assert after["awaiting"] == 0
    assert after["decisions"][0]["mine"] == {"choices": ["o2"], "note": "Once."}
    assert (listed["open_decisions"], listed["awaiting"]) == (1, 0)
    assert (refused.status_code, refused.json()["code"]) == (403, "out_of_scope")


def test_the_person_an_agent_asked_for_closes_its_decision_on_the_web(
    web: MakeWeb,
    agent: MakeAgent,
    published: str,
) -> None:
    decision = Decisions(agent()).ask(published, "Ship it?", (Option("Yes"), Option("No")))["decision_id"]
    client = web()
    sign_in(client, "sam", "Sam Okafor")

    closed = client.post(f"/api/decisions/{decision}/close", json={"outcome": "o1", "note": "Shipped."}, headers=WRITES)
    late = client.post(f"/api/decisions/{decision}/answer", json={"choices": ["o2"]}, headers=WRITES)
    bad = client.post(f"/api/decisions/{decision}/answer", json={"choices": []}, headers=WRITES)

    assert closed.json() == {"state": "closed", "seq": closed.json()["seq"]}
    assert (late.status_code, late.json()["code"]) == (409, "closed")
    assert (bad.status_code, bad.json()["code"]) == (422, "invalid")
    assert client.get("/api/decisions", params={"state": "closed"}).json()["decisions"][0]["outcome"] == "o1"
