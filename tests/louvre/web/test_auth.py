"""Signing in with GitHub, for the people on the allowlist, and by name where a deployment turns that on."""

from unittest import mock
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from louvre.core.accounts import Account
from louvre.web import github
from louvre.web.auth import STATE_COOKIE
from louvre.web.caller import SESSION_COOKIE
from tests.conftest import WRITES, MakeWeb, sign_in


def start(client: TestClient) -> str:
    """Start GitHub's flow, and return the state it sent the person away with."""
    response = client.get("/auth/github", follow_redirects=False)
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

    assert where == "/?sign_in=denied"
    assert SESSION_COOKIE not in client.cookies


def test_anyone_is_let_in_by_a_star(web: MakeWeb) -> None:
    client = web(allowed_logins=frozenset({"*"}))

    assert back(client, start(client), Account("gh:1", "mallory", "Mallory")) == "/"


@pytest.mark.parametrize("state", ["", "forged"])
def test_a_callback_without_its_state_signs_no_one_in(web: MakeWeb, state: str) -> None:
    client = web()
    start(client)

    assert back(client, state, Account("gh:583231", "ana", "Ana")) == "/?sign_in=failed"
    assert SESSION_COOKIE not in client.cookies


def test_github_refusing_the_code_signs_no_one_in(web: MakeWeb) -> None:
    client = web()
    state = start(client)

    with mock.patch.object(github, "account_for", autospec=True, side_effect=github.SignInError("bad code")):
        response = client.get("/auth/github/callback", params={"code": "x", "state": state}, follow_redirects=False)

    assert response.headers["location"] == "/?sign_in=failed"


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
