"""Louvre's Postgres (D007): where the database is, a connection to it, and its numbered migrations.

The database is named by `DATABASE_URL`, or by `POSTGRES_URL` as Vercel's Postgres integrations name it. Migrations
are the SQL files in `louvre/core/migrations/`, `NNNN_name.sql`, applied in order and recorded in
`schema_migrations`; a session-level advisory lock keeps two processes starting at once from applying one twice.
"""

import os
import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from importlib.resources import files

import psycopg
from psycopg.rows import DictRow, dict_row

#: The environment variables that name the database, the first set wins.
URL_VARIABLES = ("DATABASE_URL", "POSTGRES_URL")
#: The advisory lock migrations take, and the one every write to the store takes (louvre.core.store).
MIGRATE_LOCK = 0x10_0B_E1
#: A connection whose rows are dicts by column name.
type Connection = psycopg.Connection[DictRow]

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
    """Apply every migration the database has not had, in order.

    Returns:
        The names of those applied now.
    """
    applied_now: list[str] = []
    conn.execute("SELECT pg_advisory_lock(%s)", (MIGRATE_LOCK,))
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version integer PRIMARY KEY, name text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())",
        )
        done = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}
        for version, name, sql in migrations():
            if version in done:
                continue
            with conn.transaction():
                conn.execute(sql.encode())
                conn.execute("INSERT INTO schema_migrations (version, name) VALUES (%s, %s)", (version, name))
            applied_now.append(name)
    finally:
        conn.execute("SELECT pg_advisory_unlock(%s)", (MIGRATE_LOCK,))
    return applied_now


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
