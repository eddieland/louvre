"""Signing in and out, under `/auth`: with GitHub, for a deployment's people, or by name, for a local run (L5).

A session is a random secret in an HTTP-only cookie, `SameSite=Lax`, so a page on another site neither reads it nor
sends it with a write. GitHub's flow carries a random `state` in a cookie of its own, checked when GitHub sends the
person back, so nobody can be signed in as someone else by a link.
"""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from louvre.core import accounts
from louvre.core.accounts import AGENT_NAME, Account
from louvre.web import github
from louvre.web.caller import SESSION_COOKIE, Conn, Database, database
from louvre.web.settings import Settings

#: The cookie GitHub's `state` is kept in while the person is away approving.
STATE_COOKIE = "louvre_oauth_state"
#: How long a person has to approve Louvre on GitHub, in seconds.
STATE_SECONDS = 600

router = APIRouter(prefix="/auth")


class DevSignIn(BaseModel):
    """Who to sign in as, by name, where the deployment allows it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    login: Annotated[str, Field(min_length=1, max_length=39, pattern=r"^[a-z0-9][a-z0-9-]*$")]
    name: Annotated[str | None, Field(max_length=64)] = None


@router.get("/github")
def github_start(request: Request, found: Annotated[Database, Depends(database)]) -> RedirectResponse:
    """Send the person to GitHub to approve Louvre."""
    settings = found.settings
    if not settings.github:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "GitHub sign-in is off."})
    state = secrets.token_urlsafe(24)
    response = RedirectResponse(github.authorize_url(settings.github_client_id, _callback(request, settings), state))
    response.set_cookie(
        STATE_COOKIE,
        state,
        max_age=STATE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookies,
        path="/auth",
    )
    return response


@router.get("/github/callback")
def github_callback(
    request: Request,
    conn: Conn,
    found: Annotated[Database, Depends(database)],
    code: str = "",
    state: str = "",
) -> RedirectResponse:
    """Sign in the person GitHub sent back, if the allowlist lets them in."""
    settings = found.settings
    expected = request.cookies.get(STATE_COOKIE, "")
    if not settings.github or not code or not expected or not secrets.compare_digest(state, expected):
        return _back("failed")
    try:
        account = github.account_for(
            settings.github_client_id,
            settings.github_client_secret,
            code,
            _callback(request, settings),
        )
    except github.SignInError:
        return _back("failed")
    if not settings.allows(account.login):
        return _back("denied")
    response = _signed_in(conn, accounts.upsert_account(conn, account), settings, RedirectResponse("/", 303))
    response.delete_cookie(STATE_COOKIE, path="/auth")
    return response


@router.post("/dev")
def dev_sign_in(conn: Conn, found: Annotated[Database, Depends(database)], given: DevSignIn) -> Response:
    """Sign in as anyone, by name: only where the deployment turns it on."""
    settings = found.settings
    if not settings.dev_sign_in:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Sign-in by name is off."})
    name = (given.name or "").strip() or given.login.title()
    if not AGENT_NAME.match(name):
        raise HTTPException(status_code=422, detail={"code": "invalid", "message": "That name cannot be used."})
    account = accounts.upsert_account(conn, Account(f"dev:{given.login}", given.login, name))
    return _signed_in(conn, account, settings, Response(status_code=204))


@router.post("/sign-out")
def sign_out(request: Request, found: Annotated[Database, Depends(database)]) -> Response:
    """End the session."""
    secret = request.cookies.get(SESSION_COOKIE)
    if secret and found.configured:
        with found.opened() as held:
            if held.conn is not None:
                accounts.end_session(held.conn, secret)
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


def _callback(request: Request, settings: Settings) -> str:
    base = settings.base_url or str(request.base_url).rstrip("/")
    return f"{base}/auth/github/callback"


def _back(why: str) -> RedirectResponse:
    return RedirectResponse(f"/?sign_in={why}", 303)


def _signed_in[R: Response](conn: Conn, account: Account, settings: Settings, response: R) -> R:
    secret = accounts.start_session(conn, account.id)
    response.set_cookie(
        SESSION_COOKIE,
        secret,
        max_age=accounts.SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookies,
        path="/",
    )
    return response
