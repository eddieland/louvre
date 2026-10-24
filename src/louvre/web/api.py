"""The web UI's JSON API, under `/api`: what a person reads and writes on Louvre's pages.

Every route is the store's call, held to the request's scope (louvre.web.caller), so the web and an agent's tools
answer alike. A refusal is answered as `{"code": ..., "message": ...}`, with the status its code calls for. A write
needs the header `X-Louvre: 1`, which a form or a link from another site cannot send (louvre.web.app).
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from louvre.core import accounts, boards, demo, explorations, style
from louvre.core.decisions import MAX_OPTIONS, Decisions
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


class AnswerBody(_Body):
    """A person's answer to a decision: the options they chose, and a note."""

    choices: Annotated[list[Annotated[str, Field(max_length=16)]], Field(min_length=1, max_length=MAX_OPTIONS)]
    note: Annotated[str, Field(max_length=MAX_BODY)] = ""


class CloseBody(_Body):
    """A decision's close: the option decided on, if one was, and why."""

    outcome: Annotated[str | None, Field(max_length=16)] = None
    note: Annotated[str, Field(max_length=MAX_BODY)] = ""


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
    found: Annotated[Database, Depends(database)],
    cursor: str | None = None,
    namespace: Annotated[str | None, Query(max_length=64)] = None,
) -> dict[str, object]:
    """The artifacts the request reaches, newest first, by page: the demo's only when its namespace is named."""
    return store.overview(cursor=cursor, namespace=namespace, leave_out=_set_apart(found, namespace))


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
def board_list(
    store: Reader,
    found: Annotated[Database, Depends(database)],
    namespace: Annotated[str | None, Query(max_length=64)] = None,
) -> dict[str, object]:
    """The boards with a frame the request reaches, in `namespace` if named: the demo's only when its namespace is."""
    apart = _set_apart(found, namespace)
    listed = [b for b in _boards(found) if (namespace is None or b.namespace == namespace) and b.namespace not in apart]
    return {"boards": boards.listing(store, listed)}


@router.get("/boards/{board_id}")
def board(store: Reader, found: Annotated[Database, Depends(database)], board_id: str) -> dict[str, object]:
    """A board, and each of its frames the request reaches, with its artifact."""
    return boards.shown(store, _boards(found), board_id)


@router.get("/directions/board")
def directions_board() -> dict[str, object]:
    """The design study as a board, from the repository's pages alone: it needs no database, and takes no comments.

    Its frames are laid out as the demo's board is, each showing a direction's page as the design study serves it.
    """
    frames = [
        {
            "id": frame.id,
            "label": frame.label,
            "x": frame.x,
            "y": frame.y,
            "width": frame.width,
            "height": frame.height,
            "title": demo.DIRECTIONS[page.name],
            "src": f"/directions/{page.group}/{page.name}",
        }
        for frame in demo.BOARD.frames
        if (page := explorations.find(demo.STUDY, frame.origin["direction"])) is not None
    ]
    return {
        "board": {"id": "directions", "title": demo.BOARD.title, "namespace": "docs/ui-explorations"},
        "frames": frames,
    }


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


@router.get("/decisions")
def decision_list(
    store: Reader,
    conn: Conn,
    state: Literal["open", "closed"] | None = None,
) -> dict[str, object]:
    """The decisions the request reaches, newest first, and how many open ones await its person."""
    return _named(conn, Decisions(store).listed(state=state))


@router.get("/artifacts/{artifact_id}/decisions")
def artifact_decisions(store: Reader, conn: Conn, artifact_id: str) -> dict[str, object]:
    """An artifact's decisions, newest first."""
    return _named(conn, Decisions(store).listed(artifact_id=artifact_id))


@router.post("/decisions/{decision_id}/answer")
def answer(store: Reader, decision_id: str, given: AnswerBody) -> dict[str, object]:
    """Answer a decision, or change one's answer."""
    return Decisions(store).answer(decision_id, given.choices, given.note)


@router.post("/decisions/{decision_id}/close")
def close(store: Reader, decision_id: str, given: CloseBody) -> dict[str, object]:
    """Close a decision one asked, or that one's agent asked."""
    return Decisions(store).close(decision_id, given.outcome, given.note)


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
def house_style(kind: style.Kind = style.Kind.REPORT) -> dict[str, object]:
    """Louvre's house style for artifacts, as the `style_get` tool gives it."""
    return style.handover(kind)


def _boards(found: Database) -> tuple[boards.Board, ...]:
    """The boards there are: mock data for now, the demo's design study when the demo is on (roadmap M3)."""
    return (demo.BOARD,) if found.settings.demo else ()


def _set_apart(found: Database, namespace: str | None) -> frozenset[str]:
    """Find the namespaces a list leaves out: the demo's, which is read at `/demo`, unless it names a namespace.

    Returns:
        The demo's namespace when the demo is on and no namespace is named; none otherwise.
    """
    return frozenset({demo.NAMESPACE}) if namespace is None and found.settings.demo else frozenset()


def _named(conn: Conn, listed: dict[str, object]) -> dict[str, object]:
    """Name the person each agent that asked a decision writes for, as an agent's comment names them.

    Returns:
        `listed`, each decision's author with `on_behalf_of_name`.
    """
    found = _dicts(listed["decisions"])
    authors = [a for d in found if isinstance(a := d["author"], dict)]
    named = accounts.names(conn, {str(a["on_behalf_of"]) for a in authors if a.get("on_behalf_of")})
    for author in authors:
        author["on_behalf_of_name"] = named.get(str(author.get("on_behalf_of")))
    return listed


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
