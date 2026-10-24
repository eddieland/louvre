"""Signing in with GitHub, for the people on the allowlist, and by name where a deployment turns that on."""

from unittest import mock
from urllib.parse import parse_qs, urljoin, urlsplit

import pytest
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st

from louvre.core.accounts import Account
from louvre.web import github
from louvre.web.auth import STATE_COOKIE, local_path
from louvre.web.caller import SESSION_COOKIE
from tests.conftest import WRITES, MakeWeb, sign_in


def start(client: TestClient, then: str | None = None) -> str:
    """Start GitHub's flow, to come back to `then` if given, and return the state it sent the person away with."""
    response = client.get("/auth/github", params={} if then is None else {"next": then}, follow_redirects=False)
    assert response.status_code == 307
    where = urlsplit(response.headers["location"])
    query = parse_qs(where.query)
    assert f"{where.scheme}://{where.netloc}{where.path}" == github.AUTHORIZE_URL
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == ["https://louvre.test/auth/github/callback"]
    assert client.cookies[STATE_COOKIE] == query["state"][0]
    return query["state"][0]


def back(client: TestClient, state: str, account: Account) -> str:
    """Come back from GitHub as `account`, and return where Louvre sent the person."""
    with mock.patch.object(github, "account_for", autospec=True, return_value=account) as asked:
        response = client.get("/auth/github/callback", params={"code": "c0de", "state": state}, follow_redirects=False)
    if asked.called:
        asked.assert_called_once_with("client-id", "client-secret", "c0de", "https://louvre.test/auth/github/callback")
    assert response.status_code == 303
    return response.headers["location"]


def test_a_person_on_the_allowlist_signs_in_with_github(web: MakeWeb) -> None:
    client = web()

    where = back(client, start(client), Account("gh:583231", "Ana", "Ana Ruiz"))

    assert where == "/"
    assert client.get("/api/session").json()["account"] == {"id": "gh:583231", "login": "Ana", "name": "Ana Ruiz"}


def test_a_person_off_the_allowlist_is_turned_away(web: MakeWeb) -> None:
    client = web()

    where = back(client, start(client), Account("gh:1", "mallory", "Mallory"))

    assert where == "/sign-in?sign_in=denied"
    assert SESSION_COOKIE not in client.cookies


def test_anyone_is_let_in_by_a_star(web: MakeWeb) -> None:
    client = web(allowed_logins=frozenset({"*"}))

    assert back(client, start(client), Account("gh:1", "mallory", "Mallory")) == "/"


@pytest.mark.parametrize("state", ["", "forged"])
def test_a_callback_without_its_state_signs_no_one_in(web: MakeWeb, state: str) -> None:
    client = web()
    start(client)

    assert back(client, state, Account("gh:583231", "ana", "Ana")) == "/sign-in?sign_in=failed"
    assert SESSION_COOKIE not in client.cookies


def test_github_refusing_the_code_signs_no_one_in(web: MakeWeb) -> None:
    client = web()
    state = start(client)

    with mock.patch.object(github, "account_for", autospec=True, side_effect=github.SignInError("bad code")):
        response = client.get("/auth/github/callback", params={"code": "x", "state": state}, follow_redirects=False)

    assert response.headers["location"] == "/sign-in?sign_in=failed"


def test_a_person_comes_back_to_the_page_they_set_out_from(web: MakeWeb) -> None:
    client = web()

    where = back(client, start(client, "/a/report-1?version=2"), Account("gh:583231", "ana", "Ana"))

    assert where == "/a/report-1?version=2"


@pytest.mark.parametrize("then", ["https://evil.test/", "//evil.test/", "/\\evil.test/", "/auth/github", "a/b"])
def test_a_person_is_never_sent_off_louvre_after_signing_in(web: MakeWeb, then: str) -> None:
    client = web()

    assert back(client, start(client, then), Account("gh:583231", "ana", "Ana")) == "/"


def test_a_person_turned_away_can_try_again_from_where_they_set_out(web: MakeWeb) -> None:
    client = web()

    where = back(client, start(client, "/a/report-1"), Account("gh:1", "mallory", "Mallory"))

    assert where == "/sign-in?sign_in=denied&next=%2Fa%2Freport-1"


def test_declining_on_github_reads_as_cancelled(web: MakeWeb) -> None:
    client = web()
    state = start(client)

    response = client.get(
        "/auth/github/callback",
        params={"error": "access_denied", "state": state},
        follow_redirects=False,
    )

    assert response.headers["location"] == "/sign-in?sign_in=cancelled"
    assert SESSION_COOKIE not in client.cookies


@given(st.text())
def test_where_a_person_comes_back_to_is_always_on_louvre(then: str) -> None:
    """Whatever `next` says, the page it leads to is on Louvre's own host, as a browser reads it."""
    kept = local_path(then)
    # A browser reads a backslash as a slash, and drops tabs and newlines, before resolving a Location.
    read = kept.replace("\\", "/").replace("\t", "").replace("\n", "").replace("\r", "")
    resolved = urlsplit(urljoin("https://louvre.test/a/x", read))

    assert (resolved.scheme, resolved.netloc) == ("https", "louvre.test")
    assert not resolved.path.startswith("/auth/")


def test_github_sign_in_is_off_without_its_app(web: MakeWeb) -> None:
    client = web(github_client_id="")

    assert client.get("/auth/github", follow_redirects=False).status_code == 404
    assert client.get("/api/session").json()["sign_in"]["github"] is False


def test_sign_in_by_name_is_off_unless_turned_on(web: MakeWeb) -> None:
    client = web(dev_sign_in=False)

    assert client.post("/auth/dev", json={"login": "ana"}, headers=WRITES).status_code == 404


def test_signing_out_ends_the_session(web: MakeWeb) -> None:
    client = web()
    sign_in(client, "ana")

    assert client.post("/auth/sign-out", headers=WRITES).status_code == 204
    assert client.get("/api/session").json()["account"] is None


def test_a_session_cookie_is_http_only_and_same_site(web: MakeWeb) -> None:
    client = web(secure_cookies=True)

    response = client.post("/auth/dev", json={"login": "ana"}, headers=WRITES)

    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "secure" in cookie
