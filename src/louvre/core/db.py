"""Louvre's Postgres (D007): where the database is, a connection to it, and its numbered migrations.

The database is named by `DATABASE_URL`, or by `POSTGRES_URL` as Vercel's Postgres integrations name it. Migrations
are the SQL files in `louvre/core/migrations/`, `NNNN_name.sql`, applied in order and recorded in
`schema_migrations`; an advisory lock keeps two processes starting at once from applying one twice.

Every advisory lock Louvre takes is a transaction's, never a session's (D013): behind a pooler in transaction mode, as
Vercel's Postgres integrations name by default, each statement outside a transaction may reach a different server
connection, so a session's unlock can miss the one that holds the lock, leave it held, and hang every process after.
A transaction keeps its server connection until it ends, and its locks end with it, as they do when a process dies.
The work a lock guards runs in that same transaction: a lock held on a second connection waits holding a server
connection of the pooler's, so enough processes waiting at once leave none for the one holding the lock to work on.

Every transaction serving a request is `limited` first: a statement or a lock wait past its limit is refused as busy
(503 on the web, an error over MCP), never left to hang the request and the server connection it holds.
"""

import os
import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from importlib.resources import files

import psycopg
from psycopg.rows import DictRow, dict_row
from psycopg.sql import SQL

#: The environment variables that name the database, the first set wins.
URL_VARIABLES = ("DATABASE_URL", "POSTGRES_URL")
#: The advisory lock migrations take, and the one every write to the store takes (louvre.core.store).
MIGRATE_LOCK = 0x10_0B_E1
#: A connection whose rows are dicts by column name.
type Connection = psycopg.Connection[DictRow]
#: How long one statement may run in a transaction serving a request, and how long it may wait for a lock: past either
#: it is refused, rather than holding the request, and the server connection a pooler lent it, as long as it is let run.
STATEMENT_TIMEOUT = "15s"
LOCK_TIMEOUT = "5s"
#: How long a process starting waits for another's migrations, which may take a while; they run with no statement limit.
MIGRATE_LOCK_TIMEOUT = "60s"
#: What a statement or a lock past its limit raises: the database is too busy to answer now, and may soon be less so.
BUSY = (psycopg.errors.QueryCanceled, psycopg.errors.LockNotAvailable)
#: What Louvre says to a request refused as busy.
BUSY_MESSAGE = "Louvre is busy: try again in a moment."

_MIGRATION = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


class NotConfiguredError(RuntimeError):
    """No database is named, so nothing that needs one can be served."""


def url_from(environ: Mapping[str, str]) -> str | None:
    """Find the database's URL in `environ`.

    Returns:
        The URL, or None when no variable names one.
    """
    return next((environ[name] for name in URL_VARIABLES if environ.get(name)), None)


def database_url() -> str:
    """Find the database's URL in this process's environment.

    Returns:
        The URL.

    Raises:
        NotConfiguredError: No variable names one.
    """
    url = url_from(os.environ)
    if url is None:
        raise NotConfiguredError(f"set {' or '.join(URL_VARIABLES)} to a Postgres database")
    return url


@contextmanager
def connect(url: str) -> Iterator[Connection]:
    """Open a connection in autocommit mode: every write is a transaction the store opens itself.

    Yields:
        The connection, closed when the block ends.
    """
    with psycopg.Connection[DictRow].connect(url, autocommit=True, row_factory=dict_row) as conn:
        yield conn


def migrate(conn: Connection) -> list[str]:
    """Apply every migration the database has not had, in order, in one transaction holding the migrations' lock.

    Returns:
        The names of those applied now.
    """
    applied_now: list[str] = []
    with conn.transaction():
        conn.execute(SQL("SET LOCAL lock_timeout = {}").format(MIGRATE_LOCK_TIMEOUT))
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATE_LOCK,))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version integer PRIMARY KEY, name text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())",
        )
        done = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}
        for version, name, sql in migrations():
            if version in done:
                continue
            conn.execute(sql.encode())
            conn.execute("INSERT INTO schema_migrations (version, name) VALUES (%s, %s)", (version, name))
            applied_now.append(name)
    return applied_now


def limited(conn: Connection) -> None:
    """Hold the transaction `conn` is in to `STATEMENT_TIMEOUT` a statement and `LOCK_TIMEOUT` a lock.

    `SET LOCAL`, which ends with the transaction, so a pooler's next client of the server connection never has it. It
    takes no snapshot, so a transaction's isolation may still be set after it.
    """
    conn.execute(
        SQL("SET LOCAL statement_timeout = {}; SET LOCAL lock_timeout = {}").format(
            STATEMENT_TIMEOUT,
            LOCK_TIMEOUT,
        ),
    )


def migrations() -> list[tuple[int, str, str]]:
    """List the migrations Louvre ships, in order.

    Returns:
        Each one's version, file name, and SQL.
    """
    found: list[tuple[int, str, str]] = []
    for entry in (files("louvre.core") / "migrations").iterdir():
        match = _MIGRATION.match(entry.name)
        if match:
            found.append((int(match[1]), entry.name, entry.read_text(encoding="utf-8")))
    return sorted(found)
