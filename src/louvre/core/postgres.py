"""The store's tables in Postgres (D007): each method of `Tables` as one query on a connection.

A read is one transaction at repeatable read, so every query in it sees one snapshot. A write is one transaction that
takes an advisory lock first (`db.WRITE_LOCK`), so writes commit one at a time and in `seq` order, and a reader never
sees a `seq` before every lower one is visible: nothing appears below a cursor a reader has passed.
"""

import json
from collections.abc import Iterable, Iterator, Mapping
from collections.abc import Set as AbstractSet
from contextlib import contextmanager
from datetime import datetime
from typing import override

from louvre.core import accounts
from louvre.core.accounts import Account
from louvre.core.db import SEED_LOCK, WRITE_LOCK, Connection
from louvre.core.tables import Row, Tables
from louvre.core.text import Anchor


class PostgresTables(Tables):  # noqa: PLR0904  (one method a query: the interface is the tables')
    """The tables of the database one connection reaches."""

    def __init__(self, conn: Connection) -> None:
        """Serve `conn`'s database."""
        self._conn = conn

    @override
    @contextmanager
    def read(self) -> Iterator[None]:
        with self._conn.transaction():
            self._conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            yield

    @override
    @contextmanager
    def write(self) -> Iterator[None]:
        with self._conn.transaction():
            self._conn.execute("SELECT pg_advisory_xact_lock(%s)", (WRITE_LOCK,))
            yield

    @override
    @contextmanager
    def seeding(self) -> Iterator[None]:
        # A session lock, not a transaction's: seeding is several writes, each a transaction of its own.
        self._conn.execute("SELECT pg_advisory_lock(%s)", (SEED_LOCK,))
        try:
            yield
        finally:
            self._conn.execute("SELECT pg_advisory_unlock(%s)", (SEED_LOCK,))

    @override
    def artifact(self, artifact_id: str) -> Row | None:
        return self._conn.execute(
            "SELECT * FROM artifacts WHERE id = %s AND deleted_at IS NULL",
            (artifact_id,),
        ).fetchone()

    @override
    def insert_artifact(
        self,
        artifact_id: str,
        namespace: str,
        title: str,
        origin: Mapping[str, str],
        owner_id: str | None,
        created_at: datetime,
    ) -> None:
        self._conn.execute(
            "INSERT INTO artifacts (id, namespace, title, origin, latest_version, owner_id, created_at, updated_at)"
            " VALUES (%s, %s, %s, %s, 1, %s, %s, %s)",
            (artifact_id, namespace, title, json.dumps(dict(origin)), owner_id, created_at, created_at),
        )

    @override
    def set_latest_version(self, artifact_id: str, version: int, title: str, updated_at: datetime) -> None:
        self._conn.execute(
            "UPDATE artifacts SET latest_version = %s, title = %s, updated_at = %s WHERE id = %s",
            (version, title, updated_at, artifact_id),
        )

    @override
    def delete_artifact(self, artifact_id: str, deleted_at: datetime) -> None:
        self._conn.execute("UPDATE artifacts SET deleted_at = %s WHERE id = %s", (deleted_at, artifact_id))

    @override
    def list_artifacts(
        self,
        *,
        namespaces: AbstractSet[str] | None,
        namespace: str | None,
        before: int | None,
        origin: Mapping[str, str],
        limit: int,
    ) -> list[Row]:
        return self._conn.execute(
            "SELECT a.*, (SELECT count(*) FROM threads t WHERE t.artifact_id = a.id AND t.state = 'open')"
            " AS open_threads FROM artifacts a WHERE a.deleted_at IS NULL"
            " AND (%(all)s OR a.namespace = ANY(%(namespaces)s))"
            " AND (%(namespace)s::text IS NULL OR a.namespace = %(namespace)s)"
            " AND (%(before)s::bigint IS NULL OR a.n < %(before)s) AND a.origin @> %(filter)s::jsonb"
            " ORDER BY a.n DESC LIMIT %(limit)s",
            {"namespace": namespace, "before": before, "filter": json.dumps(dict(origin)), "limit": limit}
            | _reach(namespaces),
        ).fetchall()

    @override
    def latest_texts(self, artifact_ids: AbstractSet[str]) -> dict[str, str]:
        rows = self._conn.execute(
            "SELECT a.id, v.text FROM artifacts a JOIN versions v ON v.artifact_id = a.id AND v.n = a.latest_version"
            " WHERE a.id = ANY(%s)",
            (sorted(artifact_ids),),
        ).fetchall()
        return {str(row["id"]): str(row["text"]) for row in rows}

    @override
    def insert_version(
        self,
        artifact_id: str,
        n: int,
        content_type: str,
        sha256: str,
        content: str,
        text: str,
        created_at: datetime,
    ) -> None:
        self._conn.execute(
            "INSERT INTO versions (artifact_id, n, content_type, sha256, content, text, created_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (artifact_id, n, content_type, sha256, content, text, created_at),
        )

    @override
    def version(self, artifact_id: str, n: int) -> Row | None:
        return self._conn.execute(
            "SELECT * FROM versions WHERE artifact_id = %s AND n = %s",
            (artifact_id, n),
        ).fetchone()

    @override
    def versions(self, artifact_id: str) -> list[Row]:
        return self._conn.execute(
            "SELECT artifact_id, n, content_type, sha256, created_at FROM versions WHERE artifact_id = %s ORDER BY n",
            (artifact_id,),
        ).fetchall()

    @override
    def insert_thread(
        self,
        thread_id: str,
        artifact_id: str,
        anchor: Anchor | None,
        anchored_version: int,
        created_at: datetime,
    ) -> None:
        self._conn.execute(
            "INSERT INTO threads (id, artifact_id, exact, prefix, suffix, anchored_version, state, created_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, 'open', %s)",
            (
                thread_id,
                artifact_id,
                None if anchor is None else anchor.exact,
                None if anchor is None else anchor.prefix,
                None if anchor is None else anchor.suffix,
                anchored_version,
                created_at,
            ),
        )

    @override
    def thread(self, thread_id: str) -> Row | None:
        return self._conn.execute(
            "SELECT t.*, a.namespace FROM threads t JOIN artifacts a ON a.id = t.artifact_id"
            " WHERE t.id = %s AND a.deleted_at IS NULL",
            (thread_id,),
        ).fetchone()

    @override
    def threads(self, artifact_id: str, state: str | None) -> list[Row]:
        return self._conn.execute(
            "SELECT * FROM threads WHERE artifact_id = %s AND (%s::text IS NULL OR state = %s) ORDER BY n",
            (artifact_id, state, state),
        ).fetchall()

    @override
    def set_thread_state(self, thread_id: str, state: str) -> None:
        self._conn.execute("UPDATE threads SET state = %s WHERE id = %s", (state, thread_id))

    @override
    def insert_comment(
        self,
        comment_id: str,
        thread_id: str,
        author_id: str,
        body: str,
        created_at: datetime,
        via: str,
    ) -> None:
        self._conn.execute(
            "INSERT INTO comments (id, thread_id, seq, author_id, body, created_at, via)"
            " VALUES (%s, %s, 0, %s, %s, %s, %s)",
            (comment_id, thread_id, author_id, body, created_at, via),
        )

    @override
    def comment(self, comment_id: str) -> Row | None:
        return self._conn.execute(
            "SELECT c.*, a.namespace FROM comments c JOIN threads t ON t.id = c.thread_id"
            " JOIN artifacts a ON a.id = t.artifact_id WHERE c.id = %s AND c.deleted_at IS NULL"
            " AND a.deleted_at IS NULL",
            (comment_id,),
        ).fetchone()

    @override
    def comments(self, artifact_id: str) -> list[Row]:
        return self._conn.execute(
            "SELECT c.*, w.display_name, w.kind, w.on_behalf_of FROM comments c"
            " JOIN threads t ON t.id = c.thread_id JOIN authors w ON w.id = c.author_id"
            " WHERE t.artifact_id = %s ORDER BY c.n",
            (artifact_id,),
        ).fetchall()

    @override
    def set_comment_seq(self, comment_id: str, seq: int) -> None:
        self._conn.execute("UPDATE comments SET seq = %s WHERE id = %s", (seq, comment_id))

    @override
    def edit_comment(self, comment_id: str, body: str, edited_at: datetime) -> None:
        self._conn.execute(
            "UPDATE comments SET body = %s, edited_at = %s WHERE id = %s",
            (body, edited_at, comment_id),
        )

    @override
    def delete_comment(self, comment_id: str, deleted_at: datetime) -> None:
        self._conn.execute("UPDATE comments SET body = '', deleted_at = %s WHERE id = %s", (deleted_at, comment_id))

    @override
    def newest_seq(self) -> int:
        row = self._conn.execute("SELECT coalesce(max(seq), 0) AS newest FROM changes").fetchone()
        return int(str(row["newest"])) if row else 0

    @override
    def insert_change(
        self,
        kind: str,
        thread_id: str,
        comment_id: str | None,
        author_id: str,
        via: str,
        at: datetime,
    ) -> int:
        row = self._conn.execute(
            "INSERT INTO changes (kind, thread_id, comment_id, author_id, via, at) VALUES (%s, %s, %s, %s, %s, %s)"
            " RETURNING seq",
            (kind, thread_id, comment_id, author_id, via, at),
        ).fetchone()
        return int(str(row["seq"])) if row else 0

    @override
    def changes(
        self,
        *,
        since: int,
        through: int,
        namespaces: AbstractSet[str] | None,
        origin: Mapping[str, str],
        limit: int,
    ) -> list[Row]:
        return self._conn.execute(
            "SELECT ch.seq, ch.kind, ch.at, ch.via AS change_via, a.id AS artifact_id, a.origin,"
            " t.id AS thread_id, t.exact, t.prefix, t.suffix, t.anchored_version, t.state,"
            " c.id AS comment_id, c.body, c.created_at, c.edited_at, c.deleted_at,"
            " w.id AS author_id, w.display_name, w.kind AS author_kind, w.on_behalf_of"
            " FROM changes ch JOIN threads t ON t.id = ch.thread_id JOIN artifacts a ON a.id = t.artifact_id"
            " JOIN authors w ON w.id = ch.author_id LEFT JOIN comments c ON c.id = ch.comment_id"
            " WHERE ch.seq > %(since)s AND ch.seq <= %(through)s AND a.deleted_at IS NULL"
            " AND (%(all)s OR a.namespace = ANY(%(namespaces)s)) AND a.origin @> %(filter)s::jsonb"
            " ORDER BY ch.seq LIMIT %(limit)s",
            {"since": since, "through": through, "filter": json.dumps(dict(origin)), "limit": limit}
            | _reach(namespaces),
        ).fetchall()

    @override
    def upsert_author(self, author_id: str, display_name: str, kind: str, on_behalf_of: str | None) -> None:
        self._conn.execute(
            "INSERT INTO authors (id, display_name, kind, on_behalf_of) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO"
            " UPDATE SET display_name = excluded.display_name, kind = excluded.kind,"
            " on_behalf_of = excluded.on_behalf_of",
            (author_id, display_name, kind, on_behalf_of),
        )

    @override
    def upsert_account(self, account_id: str, login: str, display_name: str) -> None:
        accounts.upsert_account(self._conn, Account(account_id, login, display_name))

    @override
    def account_names(self, account_ids: Iterable[str]) -> dict[str, str]:
        return accounts.names(self._conn, account_ids)


def _reach(namespaces: AbstractSet[str] | None) -> dict[str, object]:
    """Bind the namespaces a scope reaches, for `(%(all)s OR a.namespace = ANY(%(namespaces)s))`.

    Returns:
        The query's parameters.
    """
    return {"all": namespaces is None, "namespaces": sorted(namespaces or ())}
