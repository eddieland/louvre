from louvre.core import db


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
