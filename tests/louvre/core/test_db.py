import re
from pathlib import Path

from louvre.core import db

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
