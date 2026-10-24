"""A person's inbox: what is new to them on the artifacts they take part in (REQUIREMENTS U11).

A person takes part in an artifact they own, which an agent of theirs published, and in one they or an agent of theirs
commented on. What is new to them there is what they have not read: a version past the last they opened, and the
comments others wrote and the threads others resolved or reopened after the last change they saw, by its `seq`
(louvre.core.store). Others are everyone but the person and their own agents, which act for them; a version is news
whoever published it, since agents publish every version. An edit or a deletion is not news: it changes what was read,
and the page shows it as it is now.

Reading an artifact's page marks it read through the `seq` its threads were read at, never through the store's newest,
so a comment that arrives while the page is open is still new on the next read. A read never moves back: an older
version opened, or an older `seq`, leaves what was read as it was.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from louvre.core.db import Connection, limited
from louvre.core.store import Row, iso

#: The most artifacts an inbox lists, the newest news first, and the most of each one's news it quotes.
MOST = 50
QUOTED = 3
#: The changes that are news.
NEWS = ("comment_created", "thread_resolved", "thread_reopened")
#: The artifacts a person takes part in: theirs, and those they or their agents commented on. `%(me)s` is the person.
_MINE = (
    "SELECT a.id FROM artifacts a WHERE a.owner_id = %(me)s AND a.deleted_at IS NULL"
    " UNION SELECT t.artifact_id FROM comments c JOIN threads t ON t.id = c.thread_id"
    " JOIN authors w ON w.id = c.author_id WHERE c.author_id = %(me)s OR w.on_behalf_of = %(me)s"
)
#: The changes on those artifacts the person has not read, by others: `artifact_id`, and the change's columns.
_NEWS = (
    "SELECT t.artifact_id, ch.seq, ch.kind, ch.at, ch.thread_id, ch.comment_id, ch.author_id"
    " FROM mine m JOIN threads t ON t.artifact_id = m.id JOIN changes ch ON ch.thread_id = t.id"
    " LEFT JOIN reads r ON r.account_id = %(me)s AND r.artifact_id = m.id"
    " JOIN authors w ON w.id = ch.author_id"
    " WHERE ch.seq > coalesce(r.seq, 0) AND ch.kind = ANY(%(news)s) AND ch.author_id <> %(me)s"
    " AND w.on_behalf_of IS DISTINCT FROM %(me)s"
)


def inbox(conn: Connection, account_id: str) -> list[dict[str, object]]:
    """List what is new to a person: each artifact they take part in with a version or a change they have not read.

    Returns:
        At most `MOST` entries, the newest news first: the artifact, the version they last read (None for none), how
        many changes and threads are new, and the newest `QUOTED` changes, each with its thread's passage and author.
    """
    params: dict[str, object] = {"me": account_id, "news": list(NEWS)}
    with conn.transaction():
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        limited(conn)
        rows = conn.execute(
            f"WITH mine AS ({_MINE}), news AS ({_NEWS}),"  # noqa: S608  (constant SQL; values are bound)
            " counted AS (SELECT artifact_id, count(*) AS unread, count(DISTINCT thread_id) AS threads,"
            " max(at) AS at FROM news GROUP BY artifact_id)"
            " SELECT a.id, a.title, a.namespace, a.origin, a.latest_version, a.created_at, r.version AS read_version,"
            " coalesce(n.unread, 0) AS unread, coalesce(n.threads, 0) AS threads,"
            " greatest(n.at, CASE WHEN a.latest_version > coalesce(r.version, 0) THEN v.created_at END) AS at"
            " FROM mine m JOIN artifacts a ON a.id = m.id AND a.deleted_at IS NULL"
            " JOIN versions v ON v.artifact_id = a.id AND v.n = a.latest_version"
            " LEFT JOIN reads r ON r.account_id = %(me)s AND r.artifact_id = a.id"
            " LEFT JOIN counted n ON n.artifact_id = a.id"
            " WHERE a.latest_version > coalesce(r.version, 0) OR n.unread > 0"
            " ORDER BY at DESC, a.n DESC LIMIT %(most)s",
            params | {"most": MOST},
        ).fetchall()
        quoted = _quoted(conn, params, [str(row["id"]) for row in rows if int(str(row["unread"]))])
    return [
        {
            "artifact": {
                "id": row["id"],
                "title": row["title"],
                "namespace": row["namespace"],
                "origin": row["origin"],
                "latest_version": row["latest_version"],
                "created_at": iso(row["created_at"]),
            },
            "read_version": row["read_version"],
            "unread": row["unread"],
            "threads": row["threads"],
            "at": iso(row["at"]),
            "news": [_news_json(change) for change in quoted if change["artifact_id"] == row["id"]],
        }
        for row in rows
    ]


def read(conn: Connection, account_id: str, artifact_id: str, *, version: int, through: int) -> None:
    """Mark that a person read `version` of an artifact, and its threads' changes through `through`.

    Neither moves back, and neither moves past what the artifact has: its latest version, the store's newest `seq`.
    """
    conn.execute(
        "INSERT INTO reads (account_id, artifact_id, version, seq, read_at)"
        " SELECT %(me)s, a.id, least(%(version)s, a.latest_version),"
        " least(%(through)s, (SELECT coalesce(max(seq), 0) FROM changes)), %(now)s"
        " FROM artifacts a WHERE a.id = %(artifact)s"
        " ON CONFLICT (account_id, artifact_id) DO UPDATE SET version = greatest(reads.version, excluded.version),"
        " seq = greatest(reads.seq, excluded.seq), read_at = excluded.read_at",
        {"me": account_id, "artifact": artifact_id, "version": version, "through": through, "now": _now()},
    )


def read_all(conn: Connection, account_id: str) -> int:
    """Mark every artifact a person takes part in read: its latest version, and every change to its threads so far.

    Returns:
        How many artifacts were marked.
    """
    with conn.transaction():
        limited(conn)
        newest = conn.execute("SELECT coalesce(max(seq), 0) AS seq FROM changes").fetchone()
        done = conn.execute(
            f"WITH mine AS ({_MINE})"  # noqa: S608  (constant SQL; values are bound)
            " INSERT INTO reads (account_id, artifact_id, version, seq, read_at)"
            " SELECT %(me)s, a.id, a.latest_version, %(seq)s, %(now)s FROM mine m JOIN artifacts a ON a.id = m.id"
            " WHERE a.deleted_at IS NULL"
            " ON CONFLICT (account_id, artifact_id) DO UPDATE SET version = greatest(reads.version, excluded.version),"
            " seq = greatest(reads.seq, excluded.seq), read_at = excluded.read_at",
            {"me": account_id, "seq": newest["seq"] if newest else 0, "now": _now()},
        )
    return done.rowcount


def unread(conn: Connection, account_id: str, artifact_id: str) -> tuple[int, set[str]]:
    """Find what is new to a person on one artifact's threads, as its page reads them.

    Returns:
        The store's newest `seq`, read first, which the page marks it read through once it has shown the threads;
        and the threads with a change new to the person, as the inbox counts them: none on an artifact they take no
        part in, where everything would be.
    """
    newest = conn.execute("SELECT coalesce(max(seq), 0) AS seq FROM changes").fetchone()
    rows = conn.execute(
        f"WITH mine AS ({_MINE})"  # noqa: S608  (constant SQL; values are bound)
        " SELECT DISTINCT ch.thread_id FROM threads t JOIN changes ch ON ch.thread_id = t.id"
        " JOIN authors w ON w.id = ch.author_id"
        " LEFT JOIN reads r ON r.account_id = %(me)s AND r.artifact_id = t.artifact_id"
        " WHERE t.artifact_id = %(artifact)s AND t.artifact_id IN (SELECT id FROM mine)"
        " AND ch.seq > coalesce(r.seq, 0) AND ch.kind = ANY(%(news)s)"
        " AND ch.author_id <> %(me)s AND w.on_behalf_of IS DISTINCT FROM %(me)s",
        {"me": account_id, "artifact": artifact_id, "news": list(NEWS)},
    ).fetchall()
    return int(str(newest["seq"])) if newest else 0, {str(row["thread_id"]) for row in rows}


def _quoted(conn: Connection, params: Mapping[str, object], artifact_ids: Sequence[str]) -> list[Row]:
    """Read the newest `QUOTED` news of each artifact named, inside the inbox's snapshot.

    Returns:
        The changes, newest first, each with its comment, its thread's passage, and its author.
    """
    if not artifact_ids:
        return []
    return conn.execute(
        f"WITH mine AS ({_MINE}), news AS ({_NEWS}),"  # noqa: S608  (constant SQL; values are bound)
        " ranked AS (SELECT *, row_number() OVER (PARTITION BY artifact_id ORDER BY seq DESC) AS k FROM news"
        " WHERE artifact_id = ANY(%(ids)s))"
        " SELECT n.artifact_id, n.seq, n.kind, n.at, n.thread_id, n.comment_id, t.exact, c.body, c.deleted_at,"
        " w.id AS author_id, w.display_name, w.kind AS author_kind, w.on_behalf_of"
        " FROM ranked n JOIN threads t ON t.id = n.thread_id JOIN authors w ON w.id = n.author_id"
        " LEFT JOIN comments c ON c.id = n.comment_id WHERE n.k <= %(quoted)s ORDER BY n.seq DESC",
        {**params, "ids": list(artifact_ids), "quoted": QUOTED},
    ).fetchall()


def _news_json(row: Row) -> dict[str, object]:
    return {
        "kind": row["kind"],
        "seq": row["seq"],
        "at": iso(row["at"]),
        "thread_id": row["thread_id"],
        "comment_id": row["comment_id"],
        "passage": row["exact"],
        "body": None if row["deleted_at"] is not None else row["body"],
        "author": {
            "id": row["author_id"],
            "display_name": row["display_name"],
            "kind": row["author_kind"],
            "on_behalf_of": row["on_behalf_of"],
        },
    }


def _now() -> datetime:
    return datetime.now(UTC)
