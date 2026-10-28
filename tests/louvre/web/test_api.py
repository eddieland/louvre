"""The web UI's API: what a person reads and writes, held to who they are."""

from unittest import mock

import pytest

from louvre.core import accounts, db, store
from louvre.core.db import Connection
from louvre.core.decisions import Decisions, Option
from louvre.core.files import File, Type
from louvre.core.text import Anchor
from louvre.web import ui
from louvre.web.app import FILE_POLICY, artifact_policy
from louvre.web.site import Site
from tests.conftest import BASE_URL, WRITES, MakeAgent, MakeWeb, lock_held, sign_in

#: The query that lists the demo's namespace, which a list leaves out unless it names it.
DEMO = {"namespace": "demo"}
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
        "site": {"name": "", "banner": [], "footer": [], "sign_in": [], "tokens": []},
    }

    sign_in(client, "ana", "Ana Ruiz")

    assert client.get("/api/session").json()["account"] == {"id": "dev:ana", "login": "ana", "name": "Ana Ruiz"}


def test_the_session_says_what_the_deployment_s_owner_says_on_its_pages(web: MakeWeb) -> None:
    client = web(site=Site(name="Acme Louvre", banner="Internal to **Acme**.", tokens="[Conventions](/wiki)"))

    said = client.get("/api/session").json()["site"]

    assert said == {
        "name": "Acme Louvre",
        "banner": [[{"text": "Internal to "}, {"text": "Acme", "strong": True}, {"text": "."}]],
        "footer": [],
        "sign_in": [],
        "tokens": [[{"text": "Conventions", "href": "/wiki"}]],
    }
    # Without a database too: the pages say it while they say what is missing.
    assert web(database_url=None, site=Site(name="Acme Louvre")).get("/api/session").json()["site"]["name"] == (
        "Acme Louvre"
    )


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

    first = client.get("/api/artifacts", params=DEMO).json()
    rest = client.get("/api/artifacts", params={**DEMO, "cursor": first["next_cursor"]}).json()
    listed = first["artifacts"] + rest["artifacts"]
    artifact = listed[-1]["id"]
    response = client.post(f"/api/artifacts/{artifact}/threads", json={"body": "Hi."}, headers=WRITES)

    assert {a["namespace"] for a in listed} == {"demo"}
    assert len(listed) == 56
    assert rest["next_cursor"] is None
    assert response.status_code == 403
    assert response.json()["code"] == "read_only"


def test_a_list_leaves_the_demo_out_unless_it_names_its_namespace(web: MakeWeb, published: str) -> None:
    reader, ana = web(demo=True), web(demo=True)
    sign_in(ana, "ana")

    assert reader.get("/api/artifacts").json()["artifacts"] == []
    assert [a["id"] for a in ana.get("/api/artifacts").json()["artifacts"]] == [published]
    assert {a["namespace"] for a in ana.get("/api/artifacts", params=DEMO).json()["artifacts"]} == {"demo"}
    assert reader.get("/api/boards").json() == {"boards": []}
    assert ana.get("/api/boards").json() == {"boards": []}
    assert [b["id"] for b in ana.get("/api/boards", params=DEMO).json()["boards"]] == [
        "design-study",
        "canopy-style",
        "canopy-structure",
    ]


def test_the_demos_report_has_a_thread_gone_from_its_second_version(web: MakeWeb) -> None:
    client = web(demo=True)
    listed = client.get("/api/artifacts", params=DEMO).json()["artifacts"]
    report = next(a for a in listed if a["latest_version"] == 2)["id"]

    threads = client.get(f"/api/artifacts/{report}/threads").json()["threads"]
    first = client.get(f"/api/artifacts/{report}/threads", params={"version": 1}).json()["threads"]

    assert [t["anchor_status"] for t in threads].count("passage_gone") == 1
    assert "passage_gone" not in [t["anchor_status"] for t in first]
    agents = [c["author"] for t in threads for c in t["comments"] if c["author"]["kind"] == "agent"]
    assert agents
    assert {a["on_behalf_of_name"] for a in agents} == {"Sam Okafor"}


def test_the_demos_report_compares_its_versions(web: MakeWeb) -> None:
    client = web(demo=True)
    listed = client.get("/api/artifacts", params=DEMO).json()["artifacts"]
    report = next(a for a in listed if a["latest_version"] == 2)["id"]

    compared = client.get(f"/api/artifacts/{report}/compare", params={"base": 1}).json()

    assert (compared["base"], compared["head"]) == (1, 2)
    assert [(c["kind"], c["removed"], c["added"]) for c in compared["changes"]] == [
        ("added", "", "The figure is from its status panel, psp.latency, for 14 to 21 October."),
        ("removed", "A day's work.", ""),
        ("changed", "60 s", "five minutes"),
    ]
    outcomes = [t["outcome"] for t in compared["threads"]]
    assert outcomes.count("passage_gone") == 1
    assert None in outcomes


@pytest.mark.parametrize(
    ("params", "status", "code"),
    [({}, 422, "invalid"), ({"base": 2}, 422, "invalid"), ({"base": 1, "head": 3}, 404, "not_found")],
)
def test_a_comparison_that_cannot_be_made_says_why(
    web: MakeWeb,
    params: dict[str, int],
    status: int,
    code: str,
) -> None:
    client = web(demo=True)
    listed = client.get("/api/artifacts", params=DEMO).json()["artifacts"]
    report = next(a for a in listed if a["latest_version"] == 2)["id"]

    response = client.get(f"/api/artifacts/{report}/compare", params=params)

    assert (response.status_code, response.json()["code"]) == (status, code)


def test_the_demos_boards_are_listed_and_shown_with_their_frames(web: MakeWeb) -> None:
    client = web(demo=True)

    listed = client.get("/api/boards", params=DEMO).json()["boards"]
    shown = client.get("/api/boards/design-study").json()

    assert listed == [
        {
            "id": "design-study",
            "title": "Design study, 2026-10-23",
            "namespace": "demo",
            "frames": 6,
            "open_threads": 2,
        },
        {
            "id": "canopy-style",
            "title": "canopy's style study, 2026-10-08",
            "namespace": "demo",
            "frames": 9,
            "open_threads": 2,
        },
        {
            "id": "canopy-structure",
            "title": "canopy's structure study, 2026-10-19",
            "namespace": "demo",
            "frames": 40,
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
    assert response.headers["content-security-policy"] == artifact_policy(BASE_URL)
    assert "allow-same-origin" not in artifact_policy(BASE_URL)
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


def test_a_version_with_files_is_served_beside_them_under_a_policy_for_them_alone(
    web: MakeWeb,
    agent: MakeAgent,
) -> None:
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    page = '<h1>Chart</h1><img src="chart.svg" alt="A chart">'
    store = agent()
    made = store.publish(
        title="Chart",
        content_type="text/html",
        content=page,
        files=[File("chart.svg", Type.SVG, svg)],
    )
    artifact = str(made["artifact_id"])
    key = store.files_key(artifact, 1)
    here = f"/content/{artifact}/1/{key}/"
    reader = web()
    sign_in(reader, "ana")

    moved = reader.get(f"/content/{artifact}/1", follow_redirects=False)
    shown = reader.get(here)
    policy = shown.headers["content-security-policy"]
    drawn = web().get(f"{here}chart.svg")

    assert moved.status_code == 307
    assert moved.headers["location"] == here
    assert shown.status_code == 200
    assert shown.text.startswith(page)
    assert policy == artifact_policy(BASE_URL, here)
    assert f"img-src data: blob: {BASE_URL}{here};" in policy
    assert f"connect-src {BASE_URL}/kit/ {BASE_URL}{here};" in policy
    assert "allow-same-origin" not in policy
    assert web().get(here).status_code == 401
    assert reader.get(f"/content/{artifact}/1/not-its-key/").status_code == 404
    # A file needs no session, as a sandboxed page's request for it carries none, but it needs the version's key.
    assert drawn.status_code == 200
    assert drawn.content == svg
    assert drawn.headers["content-type"] == "image/svg+xml"
    assert drawn.headers["content-security-policy"] == FILE_POLICY
    assert drawn.headers["access-control-allow-origin"] == "*"
    assert web().get(f"/content/{artifact}/1/not-its-key/chart.svg").status_code == 404
    assert web().get(f"{here}other.svg").status_code == 404


def test_a_version_without_files_is_served_where_it_was(web: MakeWeb, agent: MakeAgent) -> None:
    made = agent().publish(title="Plain", content_type="text/html", content="<h1>Plain</h1>")
    reader = web()
    sign_in(reader, "ana")

    shown = reader.get(f"/content/{made['artifact_id']}/1", follow_redirects=False)

    assert shown.status_code == 200
    assert shown.headers["content-security-policy"] == artifact_policy(BASE_URL)


def test_the_inbox_needs_a_sign_in(web: MakeWeb) -> None:
    client = web()

    assert client.get("/api/inbox").status_code == 401
    assert client.post("/api/inbox/read", headers=WRITES).status_code == 401


def test_a_reply_reaches_the_inbox_and_reading_the_page_clears_it(
    web: MakeWeb,
    agent: MakeAgent,
    published: str,
) -> None:
    client = web()
    sign_in(client, "ana", "Ana Ruiz")
    made = client.post(f"/api/artifacts/{published}/threads", json={"body": "Ready?"}, headers=WRITES).json()
    seen = client.get(f"/api/artifacts/{published}/threads").json()
    client.post(f"/api/artifacts/{published}/read", json={"version": 1, "through": seen["through"]}, headers=WRITES)
    assert client.get("/api/inbox").json() == {"entries": []}

    agent().reply(made["thread_id"], "Yes.")

    [entry] = client.get("/api/inbox").json()["entries"]
    assert entry["artifact"]["id"] == published
    assert entry["news"][0]["author"]["on_behalf_of_name"] == "Sam Okafor"
    shown = client.get(f"/api/artifacts/{published}/threads").json()
    assert [t["unread"] for t in shown["threads"]] == [True]
    assert shown["through"] > seen["through"]

    read = client.post(
        f"/api/artifacts/{published}/read",
        json={"version": 1, "through": shown["through"]},
        headers=WRITES,
    )

    assert read.json() == {"artifact_id": published}
    assert client.get("/api/inbox").json() == {"entries": []}
    assert [t["unread"] for t in client.get(f"/api/artifacts/{published}/threads").json()["threads"]] == [False]


def test_reading_everything_clears_the_inbox(web: MakeWeb, agent: MakeAgent, published: str) -> None:
    client = web()
    sign_in(client, "ana")
    made = client.post(f"/api/artifacts/{published}/threads", json={"body": "Ready?"}, headers=WRITES).json()
    agent().reply(made["thread_id"], "Yes.")
    assert len(client.get("/api/inbox").json()["entries"]) == 1

    assert client.post("/api/inbox/read", headers=WRITES).json() == {"artifacts": 1}

    assert client.get("/api/inbox").json() == {"entries": []}


def test_reading_an_artifact_is_refused_where_it_cannot_be_read(web: MakeWeb, published: str) -> None:
    client = web()
    sign_in(client, "ana")
    body = {"version": 1, "through": 0}

    assert client.post("/api/artifacts/a_missing/read", json=body, headers=WRITES).status_code == 404
    assert client.post(f"/api/artifacts/{published}/read", json=body).status_code == 403
    assert (
        client.post(f"/api/artifacts/{published}/read", json={"version": 0, "through": 0}, headers=WRITES).json()[
            "code"
        ]
        == "invalid"
    )


def test_a_reader_of_the_demo_has_no_news(web: MakeWeb) -> None:
    client = web(demo=True)
    listed = client.get("/api/artifacts", params={"namespace": "demo"}).json()["artifacts"]

    shown = client.get(f"/api/artifacts/{listed[0]['id']}/threads").json()

    assert shown["through"] is None
    assert {t["unread"] for t in shown["threads"]} <= {False}


def test_a_write_kept_waiting_past_its_limit_is_answered_busy(web: MakeWeb, published: str, database_url: str) -> None:
    client = web()
    sign_in(client, "ana")

    with lock_held(database_url, store.WRITE_LOCK), mock.patch.object(db, "LOCK_TIMEOUT", "100ms"):
        response = client.post(f"/api/artifacts/{published}/threads", json={"body": "Hi."}, headers=WRITES)

    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert response.json() == {"code": "busy", "message": db.BUSY_MESSAGE}
