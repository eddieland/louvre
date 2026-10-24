import re
from pathlib import Path
from unittest import mock

import psycopg
import pytest

from louvre.core import db
from tests.conftest import lock_held

#: A lock the tests hold.
KEY = 0x7E_57
#: A session's advisory lock or unlock, which a pooler in transaction mode can leave held (D013).
SESSION_LOCK = re.compile(r"pg_(?:try_)?advisory_(?:un)?lock(?:_shared)?\(")


def test_the_url_comes_from_either_variable_the_first_set_winning() -> None:
    assert db.url_from({"POSTGRES_URL": "b"}) == "b"
    assert db.url_from({"DATABASE_URL": "a", "POSTGRES_URL": "b"}) == "a"
    assert db.url_from({"DATABASE_URL": ""}) is None


def test_migrations_are_numbered_in_order() -> None:
    found = db.migrations()

    assert [version for version, _, _ in found] == list(range(1, len(found) + 1))


def test_migrating_again_applies_nothing(conn: db.Connection) -> None:
    assert db.migrate(conn) == []
    rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    assert [row["version"] for row in rows] == [v for v, _, _ in db.migrations()]


def test_no_code_takes_a_sessions_advisory_lock() -> None:
    source = Path(db.__file__).parents[1]
    found = [str(f) for f in source.rglob("*.py") if SESSION_LOCK.search(f.read_text(encoding="utf-8"))]

    assert found == [], "take a transaction's advisory lock (pg_advisory_xact_lock), never a session's (D013)"


def test_a_lock_waited_for_past_its_limit_is_refused(database_url: str, conn: db.Connection) -> None:
    with (
        lock_held(database_url, KEY),
        mock.patch.object(db, "LOCK_TIMEOUT", "100ms"),
        pytest.raises(psycopg.errors.LockNotAvailable),
    ):
        limited(conn, "SELECT pg_advisory_xact_lock(%s)", KEY)


def test_a_statement_past_its_limit_is_refused_and_the_limits_end_with_the_transaction(conn: db.Connection) -> None:
    with mock.patch.object(db, "STATEMENT_TIMEOUT", "100ms"):
        with pytest.raises(psycopg.errors.QueryCanceled):
            limited(conn, "SELECT pg_sleep(%s)", 5)
        inside = limited(conn, "SHOW statement_timeout")

    after = conn.execute("SHOW statement_timeout").fetchone()
    assert (inside, after) == ({"statement_timeout": "100ms"}, {"statement_timeout": "0"})


def limited(conn: db.Connection, query: str, *values: object) -> dict[str, object] | None:
    """Run `query` in a transaction held to Louvre's limits.

    Returns:
        Its first row, if it has one.
    """
    with conn.transaction():
        db.limited(conn)
        found = conn.execute(query.encode(), values or None)
        return found.fetchone() if found.description else None
