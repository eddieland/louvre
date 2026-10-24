"""Signing in and out, under `/auth`: with GitHub, for a deployment's people, or by name, for a local run (L5).

A session is a random secret in an HTTP-only cookie, `SameSite=Lax`, so a page on another site neither reads it nor
sends it with a write. GitHub's flow carries a random `state` in a cookie of its own, checked when GitHub sends the
person back, so nobody can be signed in as someone else by a link. The page they set out from rides in another cookie,
and they are sent back to it only if it is a page of Louvre's own.
"""

import secrets
import urllib.parse
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
#: The cookie the page to come back to is kept in, beside the state.
NEXT_COOKIE = "louvre_oauth_next"
#: How long a person has to approve Louvre on GitHub, in seconds.
STATE_SECONDS = 600

router = APIRouter(prefix="/auth")


class DevSignIn(BaseModel):
    """Who to sign in as, by name, where the deployment allows it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    login: Annotated[str, Field(min_length=1, max_length=39, pattern=r"^[a-z0-9][a-z0-9-]*$")]
    name: Annotated[str | None, Field(max_length=64)] = None


@router.get("/github")
def github_start(
    request: Request,
    found: Annotated[Database, Depends(database)],
    next: str = "/",  # noqa: A002  (the query parameter's name)
) -> RedirectResponse:
    """Send the person to GitHub to approve Louvre, to come back to `next`."""
    settings = found.settings
    if not settings.github:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "GitHub sign-in is off."})
    state = secrets.token_urlsafe(24)
    response = RedirectResponse(github.authorize_url(settings.github_client_id, _callback(request, settings), state))
    for name, value in ((STATE_COOKIE, state), (NEXT_COOKIE, urllib.parse.quote(local_path(next), safe=""))):
        response.set_cookie(
            name,
            value,
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
    *,
    code: str = "",
    state: str = "",
    error: str = "",
) -> RedirectResponse:
    """Sign in the person GitHub sent back, if the allowlist lets them in, and return them to where they set out."""
    settings = found.settings
    expected = request.cookies.get(STATE_COOKIE, "")
    then = local_path(urllib.parse.unquote(request.cookies.get(NEXT_COOKIE, "/")))
    if error == "access_denied":
        # GitHub sends the person back with this, and no code, when they decline to approve Louvre.
        return _back("cancelled", then)
    if not settings.github or not code or not expected or not secrets.compare_digest(state, expected):
        return _back("failed", then)
    try:
        account = github.account_for(
            settings.github_client_id,
            settings.github_client_secret,
            code,
            _callback(request, settings),
        )
    except github.SignInError:
        return _back("failed", then)
    if not settings.allows(account.login):
        return _back("denied", then)
    response = _signed_in(conn, accounts.upsert_account(conn, account), settings, RedirectResponse(then, 303))
    for name in (STATE_COOKIE, NEXT_COOKIE):
        response.delete_cookie(name, path="/auth")
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
        with found.opened() as conn:
            accounts.end_session(conn, secret)
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


def local_path(given: str) -> str:
    """Keep `given` as where to send a person after signing in only if it is a page of Louvre's own.

    Returns:
        `given`, or `/` when it could lead off Louvre (another host, a scheme, a backslash or control character a
        browser would read as one) or into `/auth` itself.
    """
    # One leading slash and no more is a path on this host: `//` names another host, and a browser reads a
    # backslash as a slash and drops tabs and newlines, so `/\host` and `/\t/host` would too.
    if not given.startswith("/") or given.startswith("//") or "\\" in given or not given.isprintable():
        return "/"
    path = given.split("?", 1)[0].split("#", 1)[0]
    return "/" if path == "/auth" or path.startswith("/auth/") else given


def _callback(request: Request, settings: Settings) -> str:
    base = settings.base_url or str(request.base_url).rstrip("/")
    return f"{base}/auth/github/callback"


def _back(why: str, then: str) -> RedirectResponse:
    # To the sign-in page, which says why, and not the catalogue: with the demo on, that shows no way to sign in.
    query = {"sign_in": why} | ({"next": then} if then != "/" else {})
    return RedirectResponse(f"/sign-in?{urllib.parse.urlencode(query)}", 303)


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
