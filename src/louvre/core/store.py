"""The store: artifacts, versions, threads, comments, and the feed of changes to them (canopy's artifacts contract).

Every call is held to a `Scope`: who writes, how (`web` or `mcp`), which namespaces it reads and writes, and what it
may do. A signed-in person reads every namespace and comments on the web; a token reads and writes its one namespace,
with the permissions its person gave it. The scope is set by who called, never by a tool's arguments.

Every change to a comment or a thread takes the next `seq` of one sequence across the store, inside the write that
makes it. A write takes one advisory lock just before it takes a `seq`, and holds it until it commits, so `seq`s commit
in order and a reader never sees a `seq` before every lower one is visible: nothing appears below a cursor a reader has
passed. It is the last lock a write takes (D014): writes that take no `seq`, such as a publish, never wait on it, and
those that do hold it only for their last statements. Otherwise writes wait only on the rows they change, each locked
`FOR NO KEY UPDATE` when read, never `FOR UPDATE`, which a writer holding the `seq` lock would wait on to check its
change's foreign keys. A read sees one snapshot (repeatable read).
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
from typing import Literal, Self

from psycopg.pq import TransactionStatus

from louvre.core import compare, geodata, render, search
from louvre.core.db import MIGRATE_LOCK, Connection, limited
from louvre.core.files import File, FilesError, new_key
from louvre.core.files import check as check_files
from louvre.core.files import insert as insert_files
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
#: The lock a write takes just before it takes a `seq`, so that `seq` commits in order (`Store.in_order`). Not the
#: migrations' lock, so a write never waits on one.
WRITE_LOCK = MIGRATE_LOCK + 1
#: How a write locks a row it reads to change: never `FOR UPDATE`, which the foreign key checks of a write holding the
#: `seq` lock would wait on.
_LOCKED = " FOR NO KEY UPDATE"
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
    #: The decision is closed: it takes no answer, and is not closed again.
    CLOSED = "closed"


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


class Store:  # noqa: PLR0904  (the contract's calls, and what modules built on the store share with it)
    """The store, through one connection, every call held to one scope."""

    def __init__(self, conn: Connection, scope: Scope, *, base_url: str = "") -> None:
        """Serve `conn`'s database, held to `scope`; `base_url` is where Louvre's pages are, for a version's url."""
        self._conn = conn
        self.scope = scope
        #: Where Louvre's pages are, for the links it gives.
        self.base_url = base_url.rstrip("/")

    def publish(
        self,
        *,
        title: str,
        content_type: ContentType,
        content: str,
        origin: Mapping[str, str] | None = None,
        artifact_id: str | None = None,
        files: Sequence[File] = (),
    ) -> dict[str, object]:
        """Make an artifact in the scope's home namespace, or with `artifact_id`, add a version to one.

        A version published with `files` carries them beside its content (louvre.core.files).

        Returns:
            Its id, the new version's number, and the url of its page.

        Raises:
            Refused: `read_only` without publish; `too_long` for a title, content, origin, or files over its bound;
                `invalid` for a blank title, an origin given with `artifact_id`, or a file whose path or type is
                wrong; `not_found` or `out_of_scope` for `artifact_id`.
        """
        self.require(Permission.PUBLISH)
        if self.scope.home is None:
            raise Refused(Code.READ_ONLY, "this scope publishes nowhere")
        if not title.strip():
            raise Refused(Code.INVALID, "an artifact's title must not be blank")
        bounded("title", title, MAX_TITLE)
        bounded("content", content, MAX_CONTENT)
        if content_type == geodata.GEOJSON:
            try:
                geodata.check(content)
            except geodata.GeodataError as e:
                raise Refused(Code.INVALID, f"the GeoJSON: {e}") from None
        if artifact_id is not None and origin:
            raise Refused(Code.INVALID, "an artifact's origin is set when it is made; omit it to add a version")
        try:
            check_files(files)
        except FilesError as e:
            raise Refused(Code.TOO_LONG if e.too_long else Code.INVALID, str(e)) from None
        pairs = check_origin({**(origin or {}), **self.scope.origin}) if artifact_id is None else {}
        text = render.text_of(content_type, content)
        digest = hashlib.sha256(content.encode()).hexdigest()
        now = _now()
        with self.writing():
            if artifact_id is None:
                artifact_id, version = _id("a"), 1
                self._conn.execute(
                    "INSERT INTO artifacts (id, namespace, title, origin, latest_version, owner_id, created_at,"
                    " updated_at) VALUES (%s, %s, %s, %s, 1, %s, %s, %s)",
                    (artifact_id, self.scope.home, title, json.dumps(pairs), self.scope.account_id, now, now),
                )
            else:
                version = int(str(self.artifact_row(artifact_id, locked=True)["latest_version"])) + 1
                self._conn.execute(
                    "UPDATE artifacts SET latest_version = %s, title = %s, updated_at = %s WHERE id = %s",
                    (version, title, now, artifact_id),
                )
            self._conn.execute(
                "INSERT INTO versions (artifact_id, n, content_type, sha256, content, text, created_at, files_key)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (artifact_id, version, content_type, digest, content, text, now, new_key() if files else None),
            )
            insert_files(self._conn, artifact_id, version, files)
        return {"artifact_id": artifact_id, "version": version, "url": self.url(artifact_id, version)}

    def read(self, artifact_id: str, version: int | None = None) -> dict[str, object]:
        """Read a version of an artifact, its latest unless `version` names one.

        Returns:
            The artifact, the version, its content, and its text.

        Raises:
            Refused: `not_found` or `out_of_scope` for the artifact, `not_found` for a version it does not have.
        """
        with self.reading():
            artifact = self.artifact_row(artifact_id)
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
        leave_out: AbstractSet[str] = frozenset(),
        query: str = "",
        *,
        ids: AbstractSet[str] | None = None,
    ) -> dict[str, object]:
        """List the artifacts the scope reaches for the web's list: as `artifacts`, with what the list shows.

        Args:
            origin: Pairs each artifact's origin holds.
            cursor: Where the page starts, from an earlier page.
            namespace: The one namespace to list, or None for every one the scope reaches.
            leave_out: Namespaces not to list, such as the demo's in a catalogue of people's work.
            query: Words each artifact holds, in its title, its latest version, or its comments (louvre.core.search).
            ids: The artifacts to list, by id, such as a board's frames'; None for any.

        Returns:
            A page of artifacts, each with when its latest version came, how many open threads and open decisions
            it has, and how many of those decisions await the scope's person; and the cursor of the next page. For a
            query, each artifact says where its words were `found`: its title's runs, and its passages and comments.

        Raises:
            Refused: `invalid` for a cursor this store did not give, or a query of more than `search.MAX_WORDS` words;
                `too_long` for a query over `search.MAX_QUERY` characters.
        """
        bounded("query", query, search.MAX_QUERY)
        words = search.Query.of(query)
        if len(words.words) > search.MAX_WORDS:
            raise Refused(Code.INVALID, f"a search is at most {search.MAX_WORDS} words")
        with self.reading():
            rows, more = self._listed(
                origin,
                cursor,
                namespace=namespace,
                leave_out=leave_out,
                query=words,
                ids=ids,
            )
            where = search.found(self._conn, [str(row["id"]) for row in rows], words) if words.words else {}
        listed: list[dict[str, object]] = []
        for row in rows:
            shown = {
                **_artifact_json(row),
                "updated_at": iso(row["updated_at"]),
                "open_threads": row["open_threads"],
                "open_decisions": row["open_decisions"],
                "awaiting": row["awaiting"],
            }
            if words.words:
                inside = where.get(str(row["id"]), {"passages": [], "comments": []})
                shown["found"] = {"title": words.runs(str(row["title"])), **inside}
            listed.append(shown)
        return {"artifacts": listed, "next_cursor": _next(rows, more)}

    def versions(self, artifact_id: str) -> dict[str, object]:
        """List an artifact's versions, oldest first.

        Returns:
            The artifact, each version's number, content type, and time, and whether the scope's person owns it.

        Raises:
            Refused: `not_found` or `out_of_scope` for the artifact.
        """
        with self.reading():
            artifact = self.artifact_row(artifact_id)
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

    def files_key(self, artifact_id: str, version: int) -> str | None:
        """Find the key a version's page and files are served under, for a reader who may read it.

        Returns:
            The key, or None for a version without files, which is served without one.

        Raises:
            Refused: `not_found` or `out_of_scope` for the artifact, `not_found` for the version.
        """
        with self.reading():
            self.artifact_row(artifact_id)
            row = self._conn.execute(
                "SELECT files_key FROM versions WHERE artifact_id = %s AND n = %s",
                (artifact_id, version),
            ).fetchone()
        if row is None:
            raise Refused(Code.NOT_FOUND, f"{artifact_id} has no version {version}")
        key = row["files_key"]
        return None if key is None else str(key)

    def page(self, artifact_id: str, version: int) -> str:
        """Make the page a version is shown as (louvre.core.render).

        Returns:
            The page's HTML.

        Raises:
            Refused: `not_found` or `out_of_scope` for the artifact, `not_found` for the version.
        """
        with self.reading():
            artifact = self.artifact_row(artifact_id)
            found = self._version(artifact, version)
        return render.page(_content_type(found["content_type"]), str(found["content"]), str(artifact["title"]))

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
        with self.reading():
            artifact = self.artifact_row(artifact_id)
            shown = _Shown.of(self._version(artifact, version))
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
        listed = [
            {
                **_thread_json(thread),
                "anchor_status": shown.status(thread),
                "comments": [_comment_json(c) for c in comments if c["thread_id"] == thread["id"]],
            }
            for thread in threads
        ]
        return {"artifact_id": artifact_id, "version": version or artifact["latest_version"], "threads": listed}

    def compare(self, artifact_id: str, base: int, head: int | None = None) -> dict[str, object]:
        """Say what changed from version `base` of an artifact to a later one, its latest unless `head` names one.

        Returns:
            The changes, in the later version's order, each with how to find it there; how many words they add and
            remove; the features a map's later version added, removed, or moved (louvre.core.geodata), none unless
            both are maps; and each thread on the earlier version's text or map, oldest first, with what became of its
            passage in the later: `unchanged`; `near_change` when a change is in it or within `CONTEXT` characters of
            it, as when the rest of its sentence was rewritten, or for a place, when its feature moved or a feature
            changed in or over it; or `passage_gone`; None for a thread on the whole artifact.

        Raises:
            Refused: `not_found` or `out_of_scope` for the artifact, `not_found` for a version it does not have;
                `invalid` when `base` is not before the later version; `too_long` for a version with more words than
                Louvre compares.
        """
        with self.reading():
            artifact = self.artifact_row(artifact_id)
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
        before, after = _Shown.of(earlier), _Shown.of(later)
        features = geodata.differences(before.geojson, after.geojson) if before.geojson and after.geojson else []
        outcomes: list[dict[str, object]] = []
        for thread in threads:
            if before.status(thread) == "passage_gone":
                # Its passage had left the earlier version: what became of it is no news of this change.
                continue
            outcomes.append(
                {"thread_id": thread["id"], "state": thread["state"], "outcome": _fate(thread, after, found, features)},
            )
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
            "features": [change.json() for change in features],
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
        with self.reading():
            row = self._conn.execute("SELECT coalesce(max(seq), 0) AS newest FROM changes").fetchone()
            newest = int(str(row["newest"])) if row else 0
            rows = self._conn.execute(
                "SELECT ch.seq, ch.kind, ch.at, ch.via AS change_via, a.id AS artifact_id, a.origin,"
                " t.id AS thread_id, t.exact, t.prefix, t.suffix, t.place, t.anchored_version, t.state,"
                " c.id AS comment_id, c.body, c.created_at, c.edited_at, c.deleted_at,"
                " w.id AS author_id, w.display_name, w.kind AS author_kind, w.on_behalf_of"
                " FROM changes ch JOIN threads t ON t.id = ch.thread_id JOIN artifacts a ON a.id = t.artifact_id"
                " JOIN authors w ON w.id = ch.author_id LEFT JOIN comments c ON c.id = ch.comment_id"
                " WHERE ch.seq > %(since)s AND ch.seq <= %(newest)s AND a.deleted_at IS NULL"
                " AND (%(all)s OR a.namespace = ANY(%(namespaces)s)) AND a.origin @> %(filter)s::jsonb"
                " ORDER BY ch.seq LIMIT %(limit)s",
                {"since": since, "newest": newest, "filter": json.dumps(dict(origin or {})), "limit": limit}
                | self.reach(),
            ).fetchall()
            latest = self._latest({str(row["artifact_id"]) for row in rows})
        through = int(str(rows[-1]["seq"])) if len(rows) == limit else max(newest, since)
        changes = [{**_change_json(row), "anchor_status": latest[str(row["artifact_id"])].status(row)} for row in rows]
        return [*changes, {"kind": "end", "through": through}]

    def reply(self, thread_id: str, body: str) -> dict[str, object]:
        """Reply in a thread, open or resolved.

        Returns:
            The comment's id and its `seq`.

        Raises:
            Refused: `read_only` without comment; `invalid` or `too_long` for the body; `not_found` or `out_of_scope`
                for the thread.
        """
        self.require(Permission.COMMENT)
        check_body(body)
        with self.writing():
            self._thread(thread_id)
            comment_id, seq = self._comment(thread_id, body)
        return {"comment_id": comment_id, "seq": seq}

    def comment(
        self,
        artifact_id: str,
        anchor: Anchor | None,
        body: str,
        *,
        pick: geodata.Pick | None = None,
    ) -> dict[str, object]:
        """Open a thread on a passage of an artifact's latest version, or with no anchor on the whole artifact.

        With `pick`, the thread is on a place on a GeoJSON version's map instead (louvre.core.geodata), and its anchor
        is the place's words: the feature's label, or the point's or the box's coordinates.

        Returns:
            The thread's id, its first comment's, and that comment's `seq`.

        Raises:
            Refused: `read_only` without comment; `invalid` or `too_long` for the body or the anchor, or a place on
                what is not a map; `not_found` or `out_of_scope` for the artifact; `anchor_not_found` when the
                anchor's words, or the picked feature, are not in its latest version.
        """
        self.require(Permission.COMMENT)
        check_body(body)
        if anchor is not None:
            check_anchor(anchor)
        with self.writing():
            artifact = self.artifact_row(artifact_id)
            latest = self._version(artifact, None)
            place = None if pick is None else _place(latest, pick)
            if place is not None:
                anchor = Anchor.of(place.quote())
            elif anchor is not None and locate(str(latest["text"]), anchor) is None:
                raise Refused(Code.ANCHOR_NOT_FOUND, f"the passage is not in version {latest['n']} of {artifact_id}")
            thread_id = _id("t")
            self._conn.execute(
                "INSERT INTO threads (id, artifact_id, exact, prefix, suffix, place, anchored_version, state,"
                " created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, 'open', %s)",
                (
                    thread_id,
                    artifact_id,
                    None if anchor is None else anchor.exact,
                    None if anchor is None else anchor.prefix,
                    None if anchor is None else anchor.suffix,
                    None if place is None else json.dumps(place.json()),
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
        self.require(Permission.COMMENT)
        state = "resolved" if resolved else "open"
        with self.writing():
            if self._thread(thread_id, locked=True)["state"] != state:
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
        self.require(Permission.COMMENT)
        check_body(body)
        with self.writing():
            found = self._own(comment_id, locked=True)
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
        self.require(Permission.COMMENT)
        with self.writing():
            found = self._own(comment_id, locked=True)
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
        with self.writing():
            artifact = self.artifact_row(artifact_id, locked=True)
            if artifact["owner_id"] != self.scope.account_id:
                raise Refused(Code.OUT_OF_SCOPE, f"{artifact_id} is not yours to delete")
            self._conn.execute("UPDATE artifacts SET deleted_at = %s WHERE id = %s", (_now(), artifact_id))
        return {"artifact_id": artifact_id}

    def url(self, artifact_id: str, version: int) -> str:
        """Name the page a version is shown on.

        Returns:
            Its URL on Louvre's web pages.
        """
        return f"{self.base_url}/a/{artifact_id}?v={version}"

    # What the modules built on the store (louvre.core.decisions) share with it: its transactions, its scope's checks,
    # and its records.

    @contextmanager
    def reading(self) -> Iterator[None]:
        """Read in one snapshot.

        Yields:
            Inside the transaction.

        Raises:
            Refused: `out_of_scope` when the scope may not read.
        """
        self.require(Permission.READ, Code.OUT_OF_SCOPE)
        # Only a transaction's first statement may say how it reads, so a read inside one already, such as the
        # demo's seeding, which publishes in one under its lock (D013), is a part of it.
        outer = self._conn.info.transaction_status != TransactionStatus.IDLE
        with self._conn.transaction():
            if not outer:
                self._conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            limited(self._conn)
            yield

    @contextmanager
    def writing(self) -> Iterator[None]:
        """Write in one transaction, alongside other writes: each waits only on the rows it locks, and on `in_order`.

        Yields:
            Inside the transaction, which commits when the block ends and rolls back when it raises.
        """
        with self._conn.transaction():
            limited(self._conn)
            yield

    def in_order(self) -> str:
        """Record the scope's author, then take the `seq` lock until the write commits, just before taking a `seq`.

        The author's row is locked first, as every row a write locks is: nothing waits on a row after the `seq` lock.

        Returns:
            The author's id.
        """
        author_id = self.author_id()
        self._conn.execute("SELECT pg_advisory_xact_lock(%s)", (WRITE_LOCK,))
        return author_id

    def require(self, permission: Permission, code: Code = Code.READ_ONLY) -> None:
        """Hold the scope to `permission`.

        Raises:
            Refused: `code`, `read_only` unless named, when the scope may not.
        """
        if permission not in self.scope.permissions:
            raise Refused(code, f"this scope may not {permission.value}")

    def reach(self) -> dict[str, object]:
        """Bind the namespaces the scope reaches, for `(%(all)s OR a.namespace = ANY(%(namespaces)s))`.

        Returns:
            The query's parameters.
        """
        namespaces = self.scope.namespaces
        return {"all": namespaces is None, "namespaces": sorted(namespaces or ())}

    def artifact_row(self, artifact_id: str, *, locked: bool = False) -> Row:
        """Find an artifact the scope reaches, and lock its row until the write commits if `locked`.

        Returns:
            Its row.

        Raises:
            Refused: `not_found` for no such artifact, or one deleted; `out_of_scope` for one outside the scope.
        """
        row = self._conn.execute(
            "SELECT * FROM artifacts WHERE id = %s AND deleted_at IS NULL"  # noqa: S608  (constant SQL; values are bound)
            + (_LOCKED if locked else ""),
            (artifact_id,),
        ).fetchone()
        if row is None:
            raise Refused(Code.NOT_FOUND, f"no artifact {artifact_id!r}")
        self.reaches(str(row["namespace"]), artifact_id)
        return row

    def reaches(self, namespace: str, what: str) -> None:
        """Hold a record in `namespace` to the namespaces the scope reaches, `what` naming it.

        Raises:
            Refused: `out_of_scope` outside them.
        """
        if self.scope.namespaces is not None and namespace not in self.scope.namespaces:
            raise Refused(Code.OUT_OF_SCOPE, f"{what} is outside the namespaces this scope reaches")

    @property
    def connection(self) -> Connection:
        """The connection the store reads and writes through."""
        return self._conn

    def version_text(self, artifact_id: str, n: int) -> str:
        """Read a version's text, inside a read or a write, its artifact already found in the scope.

        Returns:
            The text, as louvre.core.text reads it; empty for no such version.
        """
        row = self._conn.execute(
            "SELECT text FROM versions WHERE artifact_id = %s AND n = %s",
            (artifact_id, n),
        ).fetchone()
        return "" if row is None else str(row["text"])

    def place_in(self, artifact_id: str, n: int, pick: geodata.Pick) -> geodata.Place:
        """Find what a reader picked on a version's map, inside a read or a write, its artifact already found.

        Returns:
            The place, its words the version's own.

        Raises:
            Refused: `not_found` for no such version; `invalid` for a version that is no map, or a point or a box off
                the earth; `anchor_not_found` for a feature the version does not have.
        """
        row = self._conn.execute(
            "SELECT content_type, content FROM versions WHERE artifact_id = %s AND n = %s",
            (artifact_id, n),
        ).fetchone()
        if row is None:
            raise Refused(Code.NOT_FOUND, f"{artifact_id} has no version {n}")
        return _place(row, pick)

    def author_id(self) -> str:
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

    def _listed(
        self,
        origin: Mapping[str, str] | None,
        cursor: str | None,
        *,
        namespace: str | None,
        leave_out: AbstractSet[str] = frozenset(),
        query: search.Query = search.EVERYTHING,
        ids: AbstractSet[str] | None = None,
    ) -> tuple[list[Row], bool]:
        before = None
        if cursor is not None:
            if not (cursor.isascii() and cursor.isdigit() and len(cursor) <= _CURSOR_DIGITS):
                raise Refused(Code.INVALID, f"{cursor!r} is not a cursor this store gave")
            before = int(cursor)
        with self.reading():
            rows = self._conn.execute(
                "SELECT a.*, (SELECT count(*) FROM threads t WHERE t.artifact_id = a.id AND t.state = 'open')"
                " AS open_threads,"
                " (SELECT count(*) FROM decisions d WHERE d.artifact_id = a.id AND d.state = 'open') AS open_decisions,"
                # The open decisions that ask the scope's person, by login, and that they have not answered.
                " (SELECT count(*) FROM decisions d JOIN accounts c ON c.id = %(account)s"
                " WHERE d.artifact_id = a.id AND d.state = 'open' AND lower(c.login) = ANY(d.asked) AND NOT EXISTS"
                " (SELECT 1 FROM answers x WHERE x.decision_id = d.id AND x.account_id = c.id)) AS awaiting"
                " FROM artifacts a WHERE a.deleted_at IS NULL"
                " AND (%(all)s OR a.namespace = ANY(%(namespaces)s))"
                " AND (%(namespace)s::text IS NULL OR a.namespace = %(namespace)s)"
                " AND NOT a.namespace = ANY(%(leave_out)s)"
                " AND (%(ids)s::text[] IS NULL OR a.id = ANY(%(ids)s))"
                " AND (%(before)s::bigint IS NULL OR a.n < %(before)s) AND a.origin @> %(filter)s::jsonb"
                # Each of the query's words in the title, the latest version's text, or a comment not deleted.
                " AND NOT EXISTS (SELECT 1 FROM unnest(%(patterns)s::text[]) p WHERE NOT (a.title ~* p"
                " OR EXISTS (SELECT 1 FROM versions v WHERE v.artifact_id = a.id AND v.n = a.latest_version"
                " AND v.text ~* p)"
                " OR EXISTS (SELECT 1 FROM threads t JOIN comments c ON c.thread_id = t.id WHERE t.artifact_id = a.id"
                " AND c.deleted_at IS NULL AND c.body ~* p)))"
                " ORDER BY a.n DESC LIMIT %(limit)s",
                {
                    "namespace": namespace,
                    "leave_out": sorted(leave_out),
                    "ids": None if ids is None else sorted(ids),
                    "account": self.scope.account_id,
                    "before": before,
                    "filter": json.dumps(dict(origin or {})),
                    "patterns": query.patterns,
                    "limit": LIST_PAGE + 1,
                }
                | self.reach(),
            ).fetchall()
        return rows[:LIST_PAGE], len(rows) > LIST_PAGE

    def _latest(self, artifact_ids: AbstractSet[str]) -> dict[str, "_Shown"]:
        rows = self._conn.execute(
            "SELECT a.id, v.text, v.content_type, v.content FROM artifacts a"
            " JOIN versions v ON v.artifact_id = a.id AND v.n = a.latest_version WHERE a.id = ANY(%s)",
            (sorted(artifact_ids),),
        ).fetchall()
        return {str(row["id"]): _Shown.of(row) for row in rows}

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

    def _thread(self, thread_id: str, *, locked: bool = False) -> Row:
        """Find a thread on an artifact the scope reaches, and lock its row until the write commits if `locked`.

        Returns:
            Its row.

        Raises:
            Refused: `not_found` for no such thread, `out_of_scope` for one outside the scope.
        """
        row = self._conn.execute(
            "SELECT t.*, a.namespace FROM threads t JOIN artifacts a ON a.id = t.artifact_id"  # noqa: S608  (as above)
            " WHERE t.id = %s AND a.deleted_at IS NULL" + (f"{_LOCKED} OF t" if locked else ""),
            (thread_id,),
        ).fetchone()
        if row is None:
            raise Refused(Code.NOT_FOUND, f"no thread {thread_id!r}")
        self.reaches(str(row["namespace"]), thread_id)
        return row

    def _own(self, comment_id: str, *, locked: bool = False) -> Row:
        """Find one of the scope's own comments, not deleted, inside a write, its row locked if `locked`.

        Returns:
            Its row.

        Raises:
            Refused: `not_found` for no such comment, or one deleted; `out_of_scope` for another's.
        """
        row = self._conn.execute(
            "SELECT c.*, a.namespace FROM comments c JOIN threads t ON t.id = c.thread_id"  # noqa: S608  (as above)
            " JOIN artifacts a ON a.id = t.artifact_id WHERE c.id = %s AND c.deleted_at IS NULL"
            " AND a.deleted_at IS NULL" + (f"{_LOCKED} OF c" if locked else ""),
            (comment_id,),
        ).fetchone()
        if row is None:
            raise Refused(Code.NOT_FOUND, f"no comment {comment_id!r}")
        self.reaches(str(row["namespace"]), comment_id)
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
            (comment_id, thread_id, self.author_id(), body, _now(), self.scope.via.value),
        )
        return comment_id, self._change("comment_created", thread_id, comment_id)

    def _change(self, kind: str, thread_id: str, comment_id: str | None) -> int:
        """Record a change by the scope's author, inside a write, in `seq` order, and set its comment's `seq` to it.

        Returns:
            Its `seq`.
        """
        author_id = self.in_order()
        row = self._conn.execute(
            "INSERT INTO changes (kind, thread_id, comment_id, author_id, via, at) VALUES (%s, %s, %s, %s, %s, %s)"
            " RETURNING seq",
            (kind, thread_id, comment_id, author_id, self.scope.via.value, _now()),
        ).fetchone()
        seq = int(str(row["seq"])) if row else 0
        if comment_id is not None:
            self._conn.execute("UPDATE comments SET seq = %s WHERE id = %s", (seq, comment_id))
        return seq


def _next(rows: Sequence[Row], more: bool) -> str | None:  # noqa: FBT001
    return str(rows[-1]["n"]) if more else None


def bounded(what: str, value: str, most: int) -> None:
    """Hold a value to its bound, `what` naming it.

    Raises:
        Refused: `too_long` past `most` characters.
    """
    if len(value) > most:
        raise Refused(Code.TOO_LONG, f"the {what} is {len(value)} characters; at most {most}")


def check_body(body: str) -> None:
    """Hold a comment's body to its bounds.

    Raises:
        Refused: `invalid` for a blank body, `too_long` for a long one.
    """
    if not body.strip():
        raise Refused(Code.INVALID, "a comment's body must not be blank")
    bounded("body", body, MAX_BODY)


def check_anchor(anchor: Anchor) -> None:
    """Hold an anchor to its bounds.

    Raises:
        Refused: `invalid` for an anchor with no words, `too_long` for a part over its bound.
    """
    if not anchor.exact:
        raise Refused(Code.INVALID, "an anchor's exact must hold words")
    bounded("anchor's exact", anchor.exact, MAX_EXACT)
    bounded("anchor's prefix", anchor.prefix, CONTEXT)
    bounded("anchor's suffix", anchor.suffix, CONTEXT)


def check_origin(pairs: Mapping[str, str]) -> dict[str, str]:
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
        bounded("origin key", key, MAX_ORIGIN_KEY)
        bounded(f"origin value of {key!r}", value, MAX_ORIGIN_VALUE)
    return dict(pairs)


def _anchor(thread: Row) -> Anchor | None:
    exact = thread["exact"]
    return None if exact is None else Anchor(str(exact), str(thread["prefix"]), str(thread["suffix"]))


@dataclass(frozen=True)
class _Shown:
    """A version as a thread's anchor is looked for in it: its text, and its GeoJSON if it is a map."""

    text: str
    #: Its content, when it is GeoJSON; empty otherwise.
    geojson: str = ""

    @classmethod
    def of(cls, version: Row) -> Self:
        """Read a version's row.

        Returns:
            What its anchors are looked for in.
        """
        is_map = version["content_type"] == geodata.GEOJSON
        return cls(str(version["text"]), str(version["content"]) if is_map else "")

    def status(self, thread: Row) -> str | None:
        """Look for a thread's anchor here: its place, on a map, or its words.

        Returns:
            `found`, `passage_gone`, or None for a thread on the whole artifact.
        """
        stored = thread["place"]
        if isinstance(stored, dict):
            on_map = bool(self.geojson) and geodata.found(self.geojson, geodata.place_from(stored))
            return "found" if on_map else "passage_gone"
        anchor = _anchor(thread)
        if anchor is None:
            return None
        return "found" if locate(self.text, anchor) is not None else "passage_gone"


def _fate(
    thread: Row,
    later: _Shown,
    text: compare.Comparison,
    features: Sequence[geodata.FeatureChange],
) -> str | None:
    """Say what became of a thread's passage, or its place on a map, in a later version.

    Returns:
        `passage_gone`, `near_change`, or `unchanged`; None for a thread on the whole artifact.
    """
    status = later.status(thread)
    stored = thread["place"]
    anchor = _anchor(thread)
    if status != "found" or anchor is None:
        return status
    if isinstance(stored, dict):
        return "near_change" if geodata.near(geodata.place_from(stored), features) else "unchanged"
    at = locate(later.text, anchor) or 0
    return "near_change" if text.touches(max(0, at - CONTEXT), at + len(anchor.exact) + CONTEXT) else "unchanged"


def _place(version: Row, pick: geodata.Pick) -> geodata.Place:
    """Find what a reader picked on a version's map.

    Returns:
        The place.

    Raises:
        Refused: `invalid` for a version that is no map, or a point or a box off the earth; `anchor_not_found` for a
            feature the version does not have.
    """
    if version["content_type"] != geodata.GEOJSON:
        raise Refused(Code.INVALID, "a place is on a map: only a GeoJSON version has one")
    try:
        return geodata.place_on(str(version["content"]), pick)
    except geodata.GeodataError as e:
        code = Code.ANCHOR_NOT_FOUND if pick.kind == geodata.PlaceKind.FEATURE else Code.INVALID
        raise Refused(code, str(e)) from None


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


def _content_type(stored: object) -> ContentType:
    """Read a version's content type as the database holds it, which its check keeps to `ContentType`'s.

    Returns:
        The content type.
    """
    match stored:
        case "text/markdown":
            return "text/markdown"
        case "application/geo+json":
            return "application/geo+json"
        case _:
            return "text/html"


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
        "place": row["place"],
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
        "place": row["place"],
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
