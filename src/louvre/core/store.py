"""The store: artifacts, versions, threads, comments, and the feed of changes to them (canopy's artifacts contract).

Every call is held to a `Scope`: who writes, how (`web` or `mcp`), which namespaces it reads and writes, and what it
may do. A signed-in person reads every namespace and comments on the web; a token reads and writes its one namespace,
with the permissions its person gave it. The scope is set by who called, never by a tool's arguments.

Every change to a comment or a thread takes the next `seq` of one sequence across the store, inside the write that
makes it. Every write takes one advisory lock first, so writes commit one at a time and in `seq` order, and a reader
never sees a `seq` before every lower one is visible: nothing appears below a cursor a reader has passed. A read sees
one snapshot (repeatable read).
"""

import hashlib
import json
import secrets
from collections.abc import Iterator, Mapping, Sequence
from collections.abc import Set as AbstractSet
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from louvre.core import compare, render
from louvre.core.db import MIGRATE_LOCK, Connection
from louvre.core.text import CONTEXT, Anchor, ContentType, locate

#: The most characters of an artifact's title, a version's content, and a comment's body.
MAX_TITLE = 200
MAX_CONTENT = 2_000_000
MAX_BODY = 4000
#: The most characters of an anchor's passage: a whole section of a page.
MAX_EXACT = 4000
#: The most origin pairs an artifact carries, and the most characters of a pair's key and value.
MAX_ORIGIN = 16
MAX_ORIGIN_KEY = 64
MAX_ORIGIN_VALUE = 256
#: How many artifacts a page of a list holds, and the most changes a page of the feed may.
LIST_PAGE = 50
MAX_FEED = 200
#: The lock every write takes, so that `seq` commits in order. Not the migrations' lock, so a write never waits on one.
WRITE_LOCK = MIGRATE_LOCK + 1
#: The highest `seq` Postgres holds, in a bigint.
_MAX_SEQ = 2**63 - 1
#: The most digits of a cursor a list gives: a row's number, which Postgres holds in 64 bits.
_CURSOR_DIGITS = 18


class Code(StrEnum):
    """Why a call is refused, the code its tool error carries."""

    #: No artifact, version, comment, or thread has that id.
    NOT_FOUND = "not_found"
    #: It is outside the namespaces the scope reaches, or the scope may not read, or it is another's to change.
    OUT_OF_SCOPE = "out_of_scope"
    #: A title, content, body, anchor, or origin is over its bound.
    TOO_LONG = "too_long"
    #: The anchor's words are not in the artifact's latest version.
    ANCHOR_NOT_FOUND = "anchor_not_found"
    #: The scope may not make this write.
    READ_ONLY = "read_only"
    #: An argument the tool's schema takes, but the store cannot use: a blank body, an unreadable cursor.
    INVALID = "invalid"


class Refused(Exception):  # noqa: N818  (a tool error, not a failure)
    """A call the store refuses, with the code that says why."""

    def __init__(self, code: Code, message: str) -> None:
        """Refuse with `code`, saying why in `message`."""
        super().__init__(message)
        self.code = code


class Via(StrEnum):
    """How a comment or change arrived."""

    #: A person on Louvre's web pages.
    WEB = "web"
    #: An agent, through Louvre's MCP server, with a token.
    MCP = "mcp"


class Permission(StrEnum):
    """What a scope may do: a token's scopes, by the contract's names."""

    READ = "read"
    PUBLISH = "publish"
    COMMENT = "comment"


@dataclass(frozen=True)
class Author:
    """Who wrote a comment, or changed a thread."""

    #: Stable for the life of the account: a person's account id, or `agent:ACCOUNT:NAME` for an agent.
    id: str
    display_name: str
    kind: Literal["person", "agent"]
    #: For an agent, the account id of the person it writes for.
    on_behalf_of: str | None = None


@dataclass(frozen=True)
class Scope:
    """What every call is held to."""

    #: Who writes.
    author: Author
    #: How what it writes arrives.
    via: Via
    #: The namespaces it reads and writes; None for every one, as a signed-in person reads.
    namespaces: AbstractSet[str] | None
    #: The namespace an artifact it publishes is made in; None when it publishes nowhere.
    home: str | None
    #: What it may do.
    permissions: AbstractSet[Permission]
    #: The person it acts for, who owns what it publishes and may delete it.
    account_id: str | None = None
    #: Origin pairs set on every artifact it makes, over the caller's.
    origin: Mapping[str, str] = field(default_factory=dict[str, str])


#: A row, as the database returns it.
type Row = dict[str, object]


class Store:
    """The store, through one connection, every call held to one scope."""

    def __init__(self, conn: Connection, scope: Scope, *, base_url: str = "") -> None:
        """Serve `conn`'s database, held to `scope`; `base_url` is where Louvre's pages are, for a version's url."""
        self._conn = conn
        self.scope = scope
        self._base_url = base_url.rstrip("/")

    def publish(
        self,
        *,
        title: str,
        content_type: ContentType,
        content: str,
        origin: Mapping[str, str] | None = None,
        artifact_id: str | None = None,
    ) -> dict[str, object]:
        """Make an artifact in the scope's home namespace, or with `artifact_id`, add a version to one.

        Returns:
            Its id, the new version's number, and the url of its page.

        Raises:
            Refused: `read_only` without publish; `too_long` for a title, content, or origin over its bound;
                `invalid` for a blank title, or an origin given with `artifact_id`; `not_found` or `out_of_scope` for
                `artifact_id`.
        """
        self._may(Permission.PUBLISH)
        if self.scope.home is None:
            raise Refused(Code.READ_ONLY, "this scope publishes nowhere")
        if not title.strip():
            raise Refused(Code.INVALID, "an artifact's title must not be blank")
        _bounded("title", title, MAX_TITLE)
        _bounded("content", content, MAX_CONTENT)
        if artifact_id is not None and origin:
            raise Refused(Code.INVALID, "an artifact's origin is set when it is made; omit it to add a version")
        pairs = _origin({**(origin or {}), **self.scope.origin}) if artifact_id is None else {}
        text = render.text_of(content_type, content)
        digest = hashlib.sha256(content.encode()).hexdigest()
        now = _now()
        with self._write():
            if artifact_id is None:
                artifact_id, version = _id("a"), 1
                self._conn.execute(
                    "INSERT INTO artifacts (id, namespace, title, origin, latest_version, owner_id, created_at,"
                    " updated_at) VALUES (%s, %s, %s, %s, 1, %s, %s, %s)",
                    (artifact_id, self.scope.home, title, json.dumps(pairs), self.scope.account_id, now, now),
                )
            else:
                version = int(str(self._artifact(artifact_id)["latest_version"])) + 1
                self._conn.execute(
                    "UPDATE artifacts SET latest_version = %s, title = %s, updated_at = %s WHERE id = %s",
                    (version, title, now, artifact_id),
                )
            self._conn.execute(
                "INSERT INTO versions (artifact_id, n, content_type, sha256, content, text, created_at)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (artifact_id, version, content_type, digest, content, text, now),
            )
        return {"artifact_id": artifact_id, "version": version, "url": self.url(artifact_id, version)}

    def read(self, artifact_id: str, version: int | None = None) -> dict[str, object]:
        """Read a version of an artifact, its latest unless `version` names one.

        Returns:
            The artifact, the version, its content, and its text.

        Raises:
            Refused: `not_found` or `out_of_scope` for the artifact, `not_found` for a version it does not have.
        """
        with self._read():
            artifact = self._artifact(artifact_id)
            found = self._version(artifact, version)
        return {
            "artifact": _artifact_json(artifact),
            "version": _version_json(found),
            "content": found["content"],
            "text": found["text"],
        }

    def artifacts(self, origin: Mapping[str, str] | None = None, cursor: str | None = None) -> dict[str, object]:
        """List the artifacts the scope reaches whose origin holds every pair of `origin`, newest first, by page.

        Returns:
            A page of artifacts, and the cursor of the next page, None after the last.

        Raises:
            Refused: `invalid` for a cursor this store did not give.
        """
        rows, more = self._listed(origin, cursor, namespace=None)
        return {"artifacts": [_artifact_json(row) for row in rows], "next_cursor": _next(rows, more)}

    def overview(
        self,
        origin: Mapping[str, str] | None = None,
        cursor: str | None = None,
        namespace: str | None = None,
    ) -> dict[str, object]:
        """List the artifacts the scope reaches for the web's list: as `artifacts`, with what the list shows.

        Returns:
            A page of artifacts, each with when its latest version came and how many open threads it has, and the
            cursor of the next page.

        Raises:
            Refused: `invalid` for a cursor this store did not give.
        """
        rows, more = self._listed(origin, cursor, namespace=namespace)
        return {
            "artifacts": [
                {**_artifact_json(row), "updated_at": iso(row["updated_at"]), "open_threads": row["open_threads"]}
                for row in rows
            ],
            "next_cursor": _next(rows, more),
        }

    def versions(self, artifact_id: str) -> dict[str, object]:
        """List an artifact's versions, oldest first.

        Returns:
            The artifact, each version's number, content type, and time, and whether the scope's person owns it.

        Raises:
            Refused: `not_found` or `out_of_scope` for the artifact.
        """
        with self._read():
            artifact = self._artifact(artifact_id)
            rows = self._conn.execute(
                "SELECT artifact_id, n, content_type, sha256, created_at FROM versions WHERE artifact_id = %s"
                " ORDER BY n",
                (artifact_id,),
            ).fetchall()
        return {
            "artifact": _artifact_json(artifact),
            "versions": [_version_json(row) for row in rows],
            "owned": self.scope.account_id is not None and artifact["owner_id"] == self.scope.account_id,
        }

    def page(self, artifact_id: str, version: int) -> str:
        """Make the page a version is shown as (louvre.core.render).

        Returns:
            The page's HTML.

        Raises:
            Refused: `not_found` or `out_of_scope` for the artifact, `not_found` for the version.
        """
        with self._read():
            artifact = self._artifact(artifact_id)
            found = self._version(artifact, version)
        content_type: ContentType = "text/markdown" if found["content_type"] == "text/markdown" else "text/html"
        return render.page(content_type, str(found["content"]), str(artifact["title"]))

    def threads(
        self,
        artifact_id: str,
        *,
        state: Literal["open", "resolved"] | None = None,
        version: int | None = None,
    ) -> dict[str, object]:
        """List an artifact's threads, oldest first, each anchor looked for in a version, its latest unless named.

        Returns:
            The threads, each with its comments, oldest first, and its anchor's status there: `found`, or
            `passage_gone` when its words are not in that version; None for a thread on the whole artifact.

        Raises:
            Refused: `not_found` or `out_of_scope` for the artifact, `not_found` for a version it does not have.
        """
        with self._read():
            artifact = self._artifact(artifact_id)
            text = str(self._version(artifact, version)["text"])
            threads = self._conn.execute(
                "SELECT * FROM threads WHERE artifact_id = %s AND (%s::text IS NULL OR state = %s) ORDER BY n",
                (artifact_id, state, state),
            ).fetchall()
            comments = self._conn.execute(
                "SELECT c.*, w.display_name, w.kind, w.on_behalf_of FROM comments c"
                " JOIN threads t ON t.id = c.thread_id JOIN authors w ON w.id = c.author_id"
                " WHERE t.artifact_id = %s ORDER BY c.n",
                (artifact_id,),
            ).fetchall()
        listed: list[dict[str, object]] = []
        for thread in threads:
            anchor = _anchor(thread)
            found = None if anchor is None else "found" if locate(text, anchor) is not None else "passage_gone"
            listed.append(
                {
                    **_thread_json(thread),
                    "anchor_status": found,
                    "comments": [_comment_json(c) for c in comments if c["thread_id"] == thread["id"]],
                },
            )
        return {"artifact_id": artifact_id, "version": version or artifact["latest_version"], "threads": listed}

    def compare(self, artifact_id: str, base: int, head: int | None = None) -> dict[str, object]:
        """Say what changed from version `base` of an artifact to a later one, its latest unless `head` names one.

        Returns:
            The changes, in the later version's order, each with how to find it there; how many words they add and
            remove; and each thread on the earlier version's text, oldest first, with what became of its passage in the
            later: `unchanged`; `near_change` when a change is in it or within `CONTEXT` characters of it, as when the
            rest of its sentence was rewritten; or `passage_gone`; None for a thread on the whole artifact.

        Raises:
            Refused: `not_found` or `out_of_scope` for the artifact, `not_found` for a version it does not have;
                `invalid` when `base` is not before the later version; `too_long` for a version with more words than
                Louvre compares.
        """
        with self._read():
            artifact = self._artifact(artifact_id)
            later = self._version(artifact, head)
            if not 1 <= base < int(str(later["n"])):
                raise Refused(Code.INVALID, f"version {base} is not before version {later['n']}")
            earlier = self._version(artifact, base)
            threads = self._conn.execute(
                "SELECT * FROM threads WHERE artifact_id = %s AND anchored_version <= %s ORDER BY n",
                (artifact_id, base),
            ).fetchall()
        old, new = str(earlier["text"]), str(later["text"])
        try:
            found = compare.compare(old, new)
        except compare.TooLongError as e:
            raise Refused(Code.TOO_LONG, str(e)) from None
        outcomes: list[dict[str, object]] = []
        for thread in threads:
            anchor = _anchor(thread)
            if anchor is not None and locate(old, anchor) is None:
                # Its passage had left the text by the earlier version: what became of it is no news of this change.
                continue
            at = None if anchor is None else locate(new, anchor)
            outcome = (
                None
                if anchor is None
                else "passage_gone"
                if at is None
                else "near_change"
                if found.touches(max(0, at - CONTEXT), at + len(anchor.exact) + CONTEXT)
                else "unchanged"
            )
            outcomes.append({"thread_id": thread["id"], "state": thread["state"], "outcome": outcome})
        return {
            "artifact_id": artifact_id,
            "base": base,
            "head": later["n"],
            "changes": [
                {
                    "kind": change.kind.value,
                    "anchor": None
                    if change.anchor is None
                    else {"exact": change.anchor.exact, "prefix": change.anchor.prefix, "suffix": change.anchor.suffix},
                    "added": change.added,
                    "removed": change.removed,
                }
                for change in found.changes
            ],
            "words_added": found.words_added,
            "words_removed": found.words_removed,
            "threads": outcomes,
        }

    def feed(
        self,
        origin: Mapping[str, str] | None = None,
        since: int = 0,
        limit: int = MAX_FEED,
    ) -> list[dict[str, object]]:
        """Read the changes after `since` to the artifacts the scope reaches whose origin holds every pair of `origin`.

        Returns:
            At most `limit` changes, oldest first, then the `end` line naming the `seq` the page covers through: the
            last change's when the page is full, else the store's newest, so the next page starts past changes the
            filter left out. Each change is as the comment and thread are when read: a deleted comment's body is
            empty in every change to it, and its anchor is looked for in the artifact's latest version.

        Raises:
            Refused: `invalid` for a limit outside 1 to `MAX_FEED`, or a `since` that is no seq.
        """
        if not 1 <= limit <= MAX_FEED or not 0 <= since <= _MAX_SEQ:
            raise Refused(Code.INVALID, f"since is a seq from 0, and limit from 1 to {MAX_FEED}")
        with self._read():
            row = self._conn.execute("SELECT coalesce(max(seq), 0) AS newest FROM changes").fetchone()
            newest = int(str(row["newest"])) if row else 0
            rows = self._conn.execute(
                "SELECT ch.seq, ch.kind, ch.at, ch.via AS change_via, a.id AS artifact_id, a.origin,"
                " t.id AS thread_id, t.exact, t.prefix, t.suffix, t.anchored_version, t.state,"
                " c.id AS comment_id, c.body, c.created_at, c.edited_at, c.deleted_at,"
                " w.id AS author_id, w.display_name, w.kind AS author_kind, w.on_behalf_of"
                " FROM changes ch JOIN threads t ON t.id = ch.thread_id JOIN artifacts a ON a.id = t.artifact_id"
                " JOIN authors w ON w.id = ch.author_id LEFT JOIN comments c ON c.id = ch.comment_id"
                " WHERE ch.seq > %(since)s AND ch.seq <= %(newest)s AND a.deleted_at IS NULL"
                " AND (%(all)s OR a.namespace = ANY(%(namespaces)s)) AND a.origin @> %(filter)s::jsonb"
                " ORDER BY ch.seq LIMIT %(limit)s",
                {"since": since, "newest": newest, "filter": json.dumps(dict(origin or {})), "limit": limit}
                | self._reach(),
            ).fetchall()
            latest = self._latest_texts({str(row["artifact_id"]) for row in rows})
        through = int(str(rows[-1]["seq"])) if len(rows) == limit else max(newest, since)
        changes = [{**_change_json(row), "anchor_status": _status(latest, row)} for row in rows]
        return [*changes, {"kind": "end", "through": through}]

    def reply(self, thread_id: str, body: str) -> dict[str, object]:
        """Reply in a thread, open or resolved.

        Returns:
            The comment's id and its `seq`.

        Raises:
            Refused: `read_only` without comment; `invalid` or `too_long` for the body; `not_found` or `out_of_scope`
                for the thread.
        """
        self._may(Permission.COMMENT)
        _check_body(body)
        with self._write():
            self._thread(thread_id)
            comment_id, seq = self._comment(thread_id, body)
        return {"comment_id": comment_id, "seq": seq}

    def comment(self, artifact_id: str, anchor: Anchor | None, body: str) -> dict[str, object]:
        """Open a thread on a passage of an artifact's latest version, or with no anchor on the whole artifact.

        Returns:
            The thread's id, its first comment's, and that comment's `seq`.

        Raises:
            Refused: `read_only` without comment; `invalid` or `too_long` for the body or the anchor; `not_found` or
                `out_of_scope` for the artifact; `anchor_not_found` when the anchor's words are not in its latest
                version.
        """
        self._may(Permission.COMMENT)
        _check_body(body)
        if anchor is not None:
            _check_anchor(anchor)
        with self._write():
            artifact = self._artifact(artifact_id)
            latest = self._version(artifact, None)
            if anchor is not None and locate(str(latest["text"]), anchor) is None:
                raise Refused(Code.ANCHOR_NOT_FOUND, f"the passage is not in version {latest['n']} of {artifact_id}")
            thread_id = _id("t")
            self._conn.execute(
                "INSERT INTO threads (id, artifact_id, exact, prefix, suffix, anchored_version, state, created_at)"
                " VALUES (%s, %s, %s, %s, %s, %s, 'open', %s)",
                (
                    thread_id,
                    artifact_id,
                    None if anchor is None else anchor.exact,
                    None if anchor is None else anchor.prefix,
                    None if anchor is None else anchor.suffix,
                    latest["n"],
                    _now(),
                ),
            )
            comment_id, seq = self._comment(thread_id, body)
        return {"thread_id": thread_id, "comment_id": comment_id, "seq": seq}

    def resolve(self, thread_id: str, *, resolved: bool) -> dict[str, object]:
        """Resolve a thread, or reopen it. A thread already so is left as it is, and takes no `seq`.

        Returns:
            Its state.

        Raises:
            Refused: `read_only` without comment; `not_found` or `out_of_scope` for the thread.
        """
        self._may(Permission.COMMENT)
        state = "resolved" if resolved else "open"
        with self._write():
            if self._thread(thread_id)["state"] != state:
                self._conn.execute("UPDATE threads SET state = %s WHERE id = %s", (state, thread_id))
                self._change("thread_resolved" if resolved else "thread_reopened", thread_id, None)
        return {"state": state}

    def edit(self, comment_id: str, body: str) -> dict[str, object]:
        """Change the text of one of the scope's own comments.

        Returns:
            The change's `seq`.

        Raises:
            Refused: `read_only` without comment; `invalid` or `too_long` for the body; `not_found` for the comment,
                or one deleted; `out_of_scope` for another's.
        """
        self._may(Permission.COMMENT)
        _check_body(body)
        with self._write():
            found = self._own(comment_id)
            self._conn.execute(
                "UPDATE comments SET body = %s, edited_at = %s WHERE id = %s",
                (body, _now(), comment_id),
            )
            seq = self._change("comment_edited", str(found["thread_id"]), comment_id)
        return {"seq": seq}

    def delete(self, comment_id: str) -> dict[str, object]:
        """Delete one of the scope's own comments: its row stays, with its body empty, so the feed can say so.

        Returns:
            The change's `seq`.

        Raises:
            Refused: `read_only` without comment; `not_found` for the comment, or one deleted; `out_of_scope` for
                another's.
        """
        self._may(Permission.COMMENT)
        with self._write():
            found = self._own(comment_id)
            self._conn.execute("UPDATE comments SET body = '', deleted_at = %s WHERE id = %s", (_now(), comment_id))
            seq = self._change("comment_deleted", str(found["thread_id"]), comment_id)
        return {"seq": seq}

    def delete_artifact(self, artifact_id: str) -> dict[str, object]:
        """Delete an artifact the scope's person owns, as a person does on the web; no tool deletes one.

        Returns:
            Its id.

        Raises:
            Refused: `not_found` or `out_of_scope` for the artifact, `out_of_scope` when it is not the person's.
        """
        if self.scope.via != Via.WEB or self.scope.account_id is None:
            raise Refused(Code.READ_ONLY, "only a person deletes an artifact, on the web")
        with self._write():
            artifact = self._artifact(artifact_id)
            if artifact["owner_id"] != self.scope.account_id:
                raise Refused(Code.OUT_OF_SCOPE, f"{artifact_id} is not yours to delete")
            self._conn.execute("UPDATE artifacts SET deleted_at = %s WHERE id = %s", (_now(), artifact_id))
        return {"artifact_id": artifact_id}

    def url(self, artifact_id: str, version: int) -> str:
        """Name the page a version is shown on.

        Returns:
            Its URL on Louvre's web pages.
        """
        return f"{self._base_url}/a/{artifact_id}?v={version}"

    @contextmanager
    def _read(self) -> Iterator[None]:
        """Read in one snapshot.

        Yields:
            Inside the transaction.

        Raises:
            Refused: `out_of_scope` when the scope may not read.
        """
        self._may(Permission.READ, Code.OUT_OF_SCOPE)
        with self._conn.transaction():
            self._conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            yield

    @contextmanager
    def _write(self) -> Iterator[None]:
        """Write one at a time: the lock first, so `seq` commits in order. Each statement then reads committed rows.

        Yields:
            Inside the transaction, which commits when the block ends and rolls back when it raises.
        """
        with self._conn.transaction():
            self._conn.execute("SELECT pg_advisory_xact_lock(%s)", (WRITE_LOCK,))
            yield

    def _may(self, permission: Permission, code: Code = Code.READ_ONLY) -> None:
        if permission not in self.scope.permissions:
            raise Refused(code, f"this scope may not {permission.value}")

    def _reach(self) -> dict[str, object]:
        """Bind the namespaces the scope reaches, for `(%(all)s OR a.namespace = ANY(%(namespaces)s))`.

        Returns:
            The query's parameters.
        """
        namespaces = self.scope.namespaces
        return {"all": namespaces is None, "namespaces": sorted(namespaces or ())}

    def _listed(
        self,
        origin: Mapping[str, str] | None,
        cursor: str | None,
        *,
        namespace: str | None,
    ) -> tuple[list[Row], bool]:
        before = None
        if cursor is not None:
            if not (cursor.isascii() and cursor.isdigit() and len(cursor) <= _CURSOR_DIGITS):
                raise Refused(Code.INVALID, f"{cursor!r} is not a cursor this store gave")
            before = int(cursor)
        with self._read():
            rows = self._conn.execute(
                "SELECT a.*, (SELECT count(*) FROM threads t WHERE t.artifact_id = a.id AND t.state = 'open')"
                " AS open_threads FROM artifacts a WHERE a.deleted_at IS NULL"
                " AND (%(all)s OR a.namespace = ANY(%(namespaces)s))"
                " AND (%(namespace)s::text IS NULL OR a.namespace = %(namespace)s)"
                " AND (%(before)s::bigint IS NULL OR a.n < %(before)s) AND a.origin @> %(filter)s::jsonb"
                " ORDER BY a.n DESC LIMIT %(limit)s",
                {
                    "namespace": namespace,
                    "before": before,
                    "filter": json.dumps(dict(origin or {})),
                    "limit": LIST_PAGE + 1,
                }
                | self._reach(),
            ).fetchall()
        return rows[:LIST_PAGE], len(rows) > LIST_PAGE

    def _latest_texts(self, artifact_ids: AbstractSet[str]) -> dict[str, str]:
        rows = self._conn.execute(
            "SELECT a.id, v.text FROM artifacts a JOIN versions v ON v.artifact_id = a.id AND v.n = a.latest_version"
            " WHERE a.id = ANY(%s)",
            (sorted(artifact_ids),),
        ).fetchall()
        return {str(row["id"]): str(row["text"]) for row in rows}

    def _artifact(self, artifact_id: str) -> Row:
        """Find an artifact the scope reaches.

        Returns:
            Its row.

        Raises:
            Refused: `not_found` for no such artifact, or one deleted; `out_of_scope` for one outside the scope.
        """
        row = self._conn.execute(
            "SELECT * FROM artifacts WHERE id = %s AND deleted_at IS NULL",
            (artifact_id,),
        ).fetchone()
        if row is None:
            raise Refused(Code.NOT_FOUND, f"no artifact {artifact_id!r}")
        self._reaches(str(row["namespace"]), artifact_id)
        return row

    def _reaches(self, namespace: str, what: str) -> None:
        if self.scope.namespaces is not None and namespace not in self.scope.namespaces:
            raise Refused(Code.OUT_OF_SCOPE, f"{what} is outside the namespaces this scope reaches")

    def _version(self, artifact: Row, n: int | None) -> Row:
        """Find a version of `artifact`, its latest when `n` is None.

        Returns:
            Its row.

        Raises:
            Refused: `not_found` for a version it does not have.
        """
        row = self._conn.execute(
            "SELECT * FROM versions WHERE artifact_id = %s AND n = %s",
            (artifact["id"], artifact["latest_version"] if n is None else n),
        ).fetchone()
        if row is None:
            raise Refused(Code.NOT_FOUND, f"{artifact['id']} has no version {n}")
        return row

    def _thread(self, thread_id: str) -> Row:
        """Find a thread on an artifact the scope reaches.

        Returns:
            Its row.

        Raises:
            Refused: `not_found` for no such thread, `out_of_scope` for one outside the scope.
        """
        row = self._conn.execute(
            "SELECT t.*, a.namespace FROM threads t JOIN artifacts a ON a.id = t.artifact_id"
            " WHERE t.id = %s AND a.deleted_at IS NULL",
            (thread_id,),
        ).fetchone()
        if row is None:
            raise Refused(Code.NOT_FOUND, f"no thread {thread_id!r}")
        self._reaches(str(row["namespace"]), thread_id)
        return row

    def _own(self, comment_id: str) -> Row:
        """Find one of the scope's own comments, not deleted, inside a write.

        Returns:
            Its row.

        Raises:
            Refused: `not_found` for no such comment, or one deleted; `out_of_scope` for another's.
        """
        row = self._conn.execute(
            "SELECT c.*, a.namespace FROM comments c JOIN threads t ON t.id = c.thread_id"
            " JOIN artifacts a ON a.id = t.artifact_id WHERE c.id = %s AND c.deleted_at IS NULL"
            " AND a.deleted_at IS NULL",
            (comment_id,),
        ).fetchone()
        if row is None:
            raise Refused(Code.NOT_FOUND, f"no comment {comment_id!r}")
        self._reaches(str(row["namespace"]), comment_id)
        if row["author_id"] != self.scope.author.id:
            raise Refused(Code.OUT_OF_SCOPE, f"{comment_id} is another's comment")
        return row

    def _comment(self, thread_id: str, body: str) -> tuple[str, int]:
        """Write the scope's author's comment in a thread, and its change, inside a write.

        Returns:
            The comment's id and its `seq`.
        """
        comment_id = _id("c")
        self._conn.execute(
            "INSERT INTO comments (id, thread_id, seq, author_id, body, created_at, via)"
            " VALUES (%s, %s, 0, %s, %s, %s, %s)",
            (comment_id, thread_id, self._author(), body, _now(), self.scope.via.value),
        )
        return comment_id, self._change("comment_created", thread_id, comment_id)

    def _change(self, kind: str, thread_id: str, comment_id: str | None) -> int:
        """Record a change by the scope's author, inside a write, and set its comment's `seq` to it.

        Returns:
            Its `seq`.
        """
        row = self._conn.execute(
            "INSERT INTO changes (kind, thread_id, comment_id, author_id, via, at) VALUES (%s, %s, %s, %s, %s, %s)"
            " RETURNING seq",
            (kind, thread_id, comment_id, self._author(), self.scope.via.value, _now()),
        ).fetchone()
        seq = int(str(row["seq"])) if row else 0
        if comment_id is not None:
            self._conn.execute("UPDATE comments SET seq = %s WHERE id = %s", (seq, comment_id))
        return seq

    def _author(self) -> str:
        """Record the scope's author as it is now, inside a write.

        Returns:
            Its id.
        """
        author = self.scope.author
        self._conn.execute(
            "INSERT INTO authors (id, display_name, kind, on_behalf_of) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO"
            " UPDATE SET display_name = excluded.display_name, kind = excluded.kind,"
            " on_behalf_of = excluded.on_behalf_of",
            (author.id, author.display_name, author.kind, author.on_behalf_of),
        )
        return author.id


def _next(rows: Sequence[Row], more: bool) -> str | None:  # noqa: FBT001
    return str(rows[-1]["n"]) if more else None


def _bounded(what: str, value: str, most: int) -> None:
    if len(value) > most:
        raise Refused(Code.TOO_LONG, f"the {what} is {len(value)} characters; at most {most}")


def _check_body(body: str) -> None:
    if not body.strip():
        raise Refused(Code.INVALID, "a comment's body must not be blank")
    _bounded("body", body, MAX_BODY)


def _check_anchor(anchor: Anchor) -> None:
    if not anchor.exact:
        raise Refused(Code.INVALID, "an anchor's exact must hold words")
    _bounded("anchor's exact", anchor.exact, MAX_EXACT)
    _bounded("anchor's prefix", anchor.prefix, CONTEXT)
    _bounded("anchor's suffix", anchor.suffix, CONTEXT)


def _origin(pairs: Mapping[str, str]) -> dict[str, str]:
    """Check an artifact's origin against its bounds.

    Returns:
        The pairs.

    Raises:
        Refused: `too_long` for more than `MAX_ORIGIN` pairs, or a key or value over its bound; `invalid` for an
            empty key.
    """
    if len(pairs) > MAX_ORIGIN:
        raise Refused(Code.TOO_LONG, f"the origin has {len(pairs)} pairs; at most {MAX_ORIGIN}")
    for key, value in pairs.items():
        if not key:
            raise Refused(Code.INVALID, "an origin's key must not be empty")
        _bounded("origin key", key, MAX_ORIGIN_KEY)
        _bounded(f"origin value of {key!r}", value, MAX_ORIGIN_VALUE)
    return dict(pairs)


def _anchor(thread: Row) -> Anchor | None:
    exact = thread["exact"]
    return None if exact is None else Anchor(str(exact), str(thread["prefix"]), str(thread["suffix"]))


def _status(texts: Mapping[str, str], row: Row) -> str | None:
    anchor = _anchor(row)
    if anchor is None:
        return None
    return "found" if locate(texts[str(row["artifact_id"])], anchor) is not None else "passage_gone"


def _anchor_json(row: Row) -> dict[str, str] | None:
    anchor = _anchor(row)
    return None if anchor is None else {"exact": anchor.exact, "prefix": anchor.prefix, "suffix": anchor.suffix}


def _artifact_json(row: Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "title": row["title"],
        "namespace": row["namespace"],
        "origin": row["origin"],
        "latest_version": row["latest_version"],
        "created_at": iso(row["created_at"]),
    }


def _version_json(row: Row) -> dict[str, object]:
    return {
        "artifact_id": row["artifact_id"],
        "n": row["n"],
        "content_type": row["content_type"],
        "sha256": row["sha256"],
        "created_at": iso(row["created_at"]),
    }


def _thread_json(row: Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "artifact_id": row["artifact_id"],
        "anchor": _anchor_json(row),
        "anchored_version": row["anchored_version"],
        "state": row["state"],
    }


def _author_json(author_id: object, row: Row, kind: str = "kind") -> dict[str, object]:
    return {
        "id": author_id,
        "display_name": row["display_name"],
        "kind": row[kind],
        "on_behalf_of": row["on_behalf_of"],
    }


def _comment_json(row: Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "thread_id": row["thread_id"],
        "seq": row["seq"],
        "author": _author_json(row["author_id"], row),
        "body": row["body"],
        "created_at": iso(row["created_at"]),
        "edited_at": iso(row["edited_at"]),
        "deleted_at": iso(row["deleted_at"]),
        "via": row["via"],
    }


def _change_json(row: Row) -> dict[str, object]:
    return {
        "kind": row["kind"],
        "seq": row["seq"],
        "at": iso(row["at"]),
        "artifact_id": row["artifact_id"],
        "origin": row["origin"],
        "thread_id": row["thread_id"],
        "anchor": _anchor_json(row),
        "anchored_version": row["anchored_version"],
        "state": row["state"],
        "comment_id": row["comment_id"],
        "author": _author_json(row["author_id"], row, "author_kind"),
        "via": row["change_via"],
        "body": row["body"],
        "created_at": iso(row["created_at"]),
        "edited_at": iso(row["edited_at"]),
        "deleted_at": iso(row["deleted_at"]),
    }


def iso(value: object) -> str | None:
    """Write a time as ISO 8601 in UTC, to the millisecond, as the contract has times.

    Returns:
        The time, or None for none.
    """
    if not isinstance(value, datetime):
        return None
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _id(kind: str) -> str:
    return f"{kind}_{secrets.token_hex(8)}"


def _now() -> datetime:
    return datetime.now(UTC)
