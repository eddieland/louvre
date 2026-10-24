"""The web UI's JSON API, under `/api`: what a person reads and writes on Louvre's pages.

Every route is the store's call, held to the request's scope (louvre.web.caller), so the web and an agent's tools
answer alike. A refusal is answered as `{"code": ..., "message": ...}`, with the status its code calls for. A write
needs the header `X-Louvre: 1`, which a form or a link from another site cannot send (louvre.web.app).
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from louvre.core import accounts, boards, demo, style
from louvre.core.store import MAX_BODY, MAX_EXACT, iso
from louvre.core.text import CONTEXT, Anchor
from louvre.web.caller import SESSION_COOKIE, Conn, Database, Person, Reader, database

router = APIRouter(prefix="/api")


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AnchorBody(_Body):
    """A passage, as the bridge quotes it."""

    exact: Annotated[str, Field(min_length=1, max_length=MAX_EXACT)]
    prefix: Annotated[str, Field(max_length=CONTEXT)] = ""
    suffix: Annotated[str, Field(max_length=CONTEXT)] = ""


class ThreadBody(_Body):
    """A new thread: its first comment, on a passage or on the whole artifact."""

    anchor: AnchorBody | None = None
    body: Annotated[str, Field(max_length=MAX_BODY)]


class CommentBody(_Body):
    """A reply, or a comment's new text."""

    body: Annotated[str, Field(max_length=MAX_BODY)]


class ResolveBody(_Body):
    """Whether a thread is resolved."""

    resolved: bool


class TokenBody(_Body):
    """A token to mint."""

    name: Annotated[str, Field(max_length=64)]
    namespace: Annotated[str, Field(max_length=64)]
    scopes: Annotated[list[Literal["read", "publish", "comment"]], Field(min_length=1, max_length=3)]


@router.get("/session")
def session(request: Request, found: Annotated[Database, Depends(database)]) -> dict[str, object]:
    """Who is signed in, how one can sign in, and whether the deployment has its database.

    The one route that answers without a database, so the UI can say what is missing.
    """
    settings = found.settings
    account = None
    secret = request.cookies.get(SESSION_COOKIE)
    if found.configured and secret:
        with found.opened() as conn:
            account = accounts.session_account(conn, secret)
    return {
        "account": None
        if account is None
        else {"id": account.id, "login": account.login, "name": account.display_name},
        "configured": found.configured,
        "demo": settings.demo,
        "sign_in": {"github": settings.github, "dev": settings.dev_sign_in},
    }


@router.get("/artifacts")
def artifacts(
    store: Reader,
    cursor: str | None = None,
    namespace: Annotated[str | None, Query(max_length=64)] = None,
) -> dict[str, object]:
    """The artifacts the request reaches, newest first, a page at a time."""
    return store.overview(cursor=cursor, namespace=namespace)


@router.get("/artifacts/{artifact_id}")
def artifact(store: Reader, artifact_id: str) -> dict[str, object]:
    """An artifact and its versions."""
    return store.versions(artifact_id)


@router.get("/artifacts/{artifact_id}/threads")
def threads(
    store: Reader,
    conn: Conn,
    artifact_id: str,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> dict[str, object]:
    """An artifact's threads, each anchor looked for in a version, an agent's comments with whom it writes for."""
    found = store.threads(artifact_id, version=version)
    comments = [c for t in _dicts(found["threads"]) for c in _dicts(t["comments"])]
    behalf = {
        str(a["on_behalf_of"]) for c in comments if (a := c["author"]) and isinstance(a, dict) and a.get("on_behalf_of")
    }
    named = accounts.names(conn, behalf)
    for comment in comments:
        author = comment["author"]
        if isinstance(author, dict):
            author["on_behalf_of_name"] = named.get(str(author.get("on_behalf_of")))
    return found


@router.post("/artifacts/{artifact_id}/threads", status_code=201)
def create_thread(store: Reader, artifact_id: str, given: ThreadBody) -> dict[str, object]:
    """Start a thread on an artifact's latest version."""
    anchor = None if given.anchor is None else Anchor.of(given.anchor.exact, given.anchor.prefix, given.anchor.suffix)
    return store.comment(artifact_id, anchor, given.body)


@router.delete("/artifacts/{artifact_id}")
def delete_artifact(store: Reader, artifact_id: str) -> dict[str, object]:
    """Delete an artifact its person owns."""
    return store.delete_artifact(artifact_id)


@router.get("/boards")
def board_list(store: Reader, found: Annotated[Database, Depends(database)]) -> dict[str, object]:
    """The boards with a frame the request reaches."""
    return {"boards": boards.listing(store, _boards(found))}


@router.get("/boards/{board_id}")
def board(store: Reader, found: Annotated[Database, Depends(database)], board_id: str) -> dict[str, object]:
    """A board, and each of its frames the request reaches, with its artifact."""
    return boards.shown(store, _boards(found), board_id)


@router.post("/threads/{thread_id}/replies", status_code=201)
def reply(store: Reader, thread_id: str, given: CommentBody) -> dict[str, object]:
    """Reply in a thread."""
    return store.reply(thread_id, given.body)


@router.post("/threads/{thread_id}/resolve")
def resolve(store: Reader, thread_id: str, given: ResolveBody) -> dict[str, object]:
    """Resolve a thread, or reopen it."""
    return store.resolve(thread_id, resolved=given.resolved)


@router.patch("/comments/{comment_id}")
def edit(store: Reader, comment_id: str, given: CommentBody) -> dict[str, object]:
    """Change a comment of one's own."""
    return store.edit(comment_id, given.body)


@router.delete("/comments/{comment_id}")
def delete(store: Reader, comment_id: str) -> dict[str, object]:
    """Delete a comment of one's own."""
    return store.delete(comment_id)


@router.get("/tokens")
def tokens(conn: Conn, person: Person) -> dict[str, object]:
    """The signed-in person's tokens, newest first."""
    return {"tokens": [_token_json(t) for t in accounts.tokens(conn, person)]}


@router.post("/tokens", status_code=201)
def mint(conn: Conn, person: Person, given: TokenBody) -> dict[str, object]:
    """Mint a token: its secret is in this answer and never again."""
    try:
        token, secret = accounts.mint(conn, person, given.name, given.namespace, set(given.scopes))
    except accounts.InvalidError as e:
        raise HTTPException(status_code=422, detail={"code": "invalid", "message": str(e)}) from None
    return {"token": _token_json(token), "secret": secret}


@router.delete("/tokens/{token_id}")
def revoke(conn: Conn, person: Person, token_id: str) -> dict[str, object]:
    """Revoke one of the signed-in person's tokens."""
    if not accounts.revoke(conn, person, token_id):
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": f"no token {token_id} to revoke"})
    return {"token_id": token_id}


@router.get("/style")
def house_style() -> dict[str, str]:
    """Louvre's house style for artifacts, as the `style_get` tool gives it."""
    return {"version": style.VERSION, "css": style.CSS, "rules": style.RULES}


def _boards(found: Database) -> tuple[boards.Board, ...]:
    """The boards there are: mock data for now, the demo's design study when the demo is on (roadmap M3)."""
    return (demo.BOARD,) if found.settings.demo else ()


def _dicts(value: object) -> list[dict[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _token_json(token: accounts.Token) -> dict[str, object]:
    return {
        "id": token.id,
        "name": token.name,
        "namespace": token.namespace,
        "scopes": sorted(token.scopes),
        "created_at": iso(token.created_at),
        "last_used_at": iso(token.last_used_at),
        "revoked_at": iso(token.revoked_at),
    }
