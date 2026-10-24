"""The web UI's JSON API, under `/api`: what a person reads and writes on Louvre's pages.

Every route is the store's call, held to the request's scope (louvre.web.caller), so the web and an agent's tools
answer alike. A refusal is answered as `{"code": ..., "message": ...}`, with the status its code calls for. A write
needs the header `X-Louvre: 1`, which a form or a link from another site cannot send (louvre.web.app).
"""

from collections.abc import Sequence
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from louvre.core import accounts, boards, demo, explorations, geodata, inbox, style
from louvre.core.decisions import MAX_OPTIONS, Decisions
from louvre.core.store import MAX_BODY, MAX_EXACT, iso
from louvre.core.text import CONTEXT, Anchor
from louvre.web.caller import SESSION_COOKIE, Conn, Database, Person, Reader, Viewer, database

router = APIRouter(prefix="/api")


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AnchorBody(_Body):
    """A passage, as the bridge quotes it."""

    exact: Annotated[str, Field(min_length=1, max_length=MAX_EXACT)]
    prefix: Annotated[str, Field(max_length=CONTEXT)] = ""
    suffix: Annotated[str, Field(max_length=CONTEXT)] = ""


class PlaceBody(_Body):
    """A place on a map, as the kit reports a tap on it: a feature by its id, or a point by its coordinates."""

    kind: geodata.PlaceKind
    #: The feature's id, as the page's map names it.
    id: Annotated[str, Field(max_length=MAX_EXACT)] = ""
    #: The point's longitude and latitude.
    coordinates: Annotated[tuple[float, float] | None, Field()] = None


class ThreadBody(_Body):
    """A new thread: its first comment, on a passage, on a place on a map, or on the whole artifact."""

    anchor: AnchorBody | None = None
    place: PlaceBody | None = None
    body: Annotated[str, Field(max_length=MAX_BODY)]


class CommentBody(_Body):
    """A reply, or a comment's new text."""

    body: Annotated[str, Field(max_length=MAX_BODY)]


class ResolveBody(_Body):
    """Whether a thread is resolved."""

    resolved: bool


class ReadBody(_Body):
    """What a person has read of an artifact: the version shown, and the `seq` its threads were read at."""

    version: Annotated[int, Field(ge=1)]
    through: Annotated[int, Field(ge=0)]


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
    account: Viewer,
    artifact_id: str,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> dict[str, object]:
    """An artifact's threads, each anchor looked for in a version, an agent's comments with whom it writes for.

    For a signed-in person, each thread says whether it has news for them (louvre.core.inbox), and `through` is the
    `seq` to mark the artifact read through once they have been shown: read before the threads, so it covers no
    change the threads leave out.
    """
    through, fresh = (None, set[str]()) if account is None else inbox.unread(conn, account.id, artifact_id)
    found = store.threads(artifact_id, version=version)
    listed = _dicts(found["threads"])
    for thread in listed:
        thread["unread"] = thread["id"] in fresh
    _name_agents(conn, [c["author"] for t in listed for c in _dicts(t["comments"])])
    return {**found, "through": through}


@router.post("/artifacts/{artifact_id}/read")
def read(store: Reader, conn: Conn, person: Person, artifact_id: str, given: ReadBody) -> dict[str, object]:
    """Mark an artifact read by the signed-in person: the version shown, and its threads through `through`."""
    store.versions(artifact_id)
    inbox.read(conn, person.id, artifact_id, version=given.version, through=given.through)
    return {"artifact_id": artifact_id}


@router.post("/artifacts/{artifact_id}/threads", status_code=201)
def create_thread(store: Reader, artifact_id: str, given: ThreadBody) -> dict[str, object]:
    """Start a thread on an artifact's latest version: on a passage, a place on its map, or the whole of it."""
    anchor = None if given.anchor is None else Anchor.of(given.anchor.exact, given.anchor.prefix, given.anchor.suffix)
    place = given.place
    pick = None if place is None else geodata.Pick(place.kind, place.id, place.coordinates or ())
    return store.comment(artifact_id, anchor, given.body, pick=pick)


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


@router.get("/inbox")
def news(conn: Conn, person: Person) -> dict[str, object]:
    """What is new to the signed-in person on the artifacts they take part in, the newest first."""
    entries = inbox.inbox(conn, person.id)
    _name_agents(conn, [n["author"] for e in entries for n in _dicts(e["news"])])
    return {"entries": entries}


@router.post("/inbox/read")
def read_everything(conn: Conn, person: Person) -> dict[str, object]:
    """Mark everything in the signed-in person's inbox read."""
    return {"artifacts": inbox.read_all(conn, person.id)}


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
    """The boards there are: mock data for now, the demo's design studies when the demo is on (roadmap M3)."""
    return demo.BOARDS if found.settings.demo else ()


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
    _name_agents(conn, [d["author"] for d in _dicts(listed["decisions"])])
    return listed


def _name_agents(conn: Conn, authors: Sequence[object]) -> None:
    """Name the person each agent among `authors` writes for, as `on_behalf_of_name`, where Louvre knows them."""
    found = [author for author in authors if isinstance(author, dict)]
    named = accounts.names(conn, {str(a["on_behalf_of"]) for a in found if a.get("on_behalf_of")})
    for author in found:
        author["on_behalf_of_name"] = named.get(str(author.get("on_behalf_of")))


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
