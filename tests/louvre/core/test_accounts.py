from datetime import UTC, datetime, timedelta

import pytest

from louvre.core import accounts
from louvre.core.db import Connection
from louvre.core.postgres import PostgresTables
from louvre.core.store import Permission
from tests.conftest import person


def test_a_session_signs_its_person_in_until_it_ends(conn: Connection) -> None:
    ana = person(PostgresTables(conn), "ana")
    secret = accounts.start_session(conn, ana.id)

    assert accounts.session_account(conn, secret) == ana
    accounts.end_session(conn, secret)
    assert accounts.session_account(conn, secret) is None


def test_an_expired_session_signs_no_one_in(conn: Connection) -> None:
    ana = person(PostgresTables(conn), "ana")
    secret = accounts.start_session(conn, ana.id)
    conn.execute("UPDATE sessions SET expires_at = %s", (datetime.now(UTC) - timedelta(minutes=1),))

    assert accounts.session_account(conn, secret) is None


def test_only_hashes_of_secrets_are_kept(conn: Connection) -> None:
    ana = person(PostgresTables(conn), "ana")
    session = accounts.start_session(conn, ana.id)
    _, token = accounts.mint(conn, ana, "agent", "canopy/ana", {"read"})

    stored = str(
        conn.execute("SELECT (SELECT array_agg(token_hash) FROM sessions) AS s, secret_hash FROM tokens").fetchone(),
    )

    assert session not in stored
    assert token not in stored
    assert token.startswith(accounts.TOKEN_PREFIX)


def test_a_token_gives_its_agent_a_scope_until_revoked(conn: Connection) -> None:
    ana = person(PostgresTables(conn), "ana", "Ana Ruiz")
    minted, secret = accounts.mint(conn, ana, "canopy worker", "canopy/ana", {"read", "comment"})

    scope = accounts.token_scope(conn, secret)

    assert scope is not None
    assert scope.namespaces == {"canopy/ana"}
    assert scope.home == "canopy/ana"
    assert scope.permissions == {Permission.READ, Permission.COMMENT}
    assert scope.author.kind == "agent"
    assert scope.author.on_behalf_of == ana.id
    [listed] = accounts.tokens(conn, ana)
    assert listed.id == minted.id
    assert listed.last_used_at is not None
    assert accounts.revoke(conn, ana, minted.id)
    assert not accounts.revoke(conn, ana, minted.id)
    assert accounts.token_scope(conn, secret) is None


def test_only_its_person_revokes_a_token(conn: Connection) -> None:
    ana, raj = person(PostgresTables(conn), "ana"), person(PostgresTables(conn), "raj")
    minted, secret = accounts.mint(conn, ana, "agent", "canopy/ana", {"read"})

    assert not accounts.revoke(conn, raj, minted.id)
    assert accounts.token_scope(conn, secret) is not None


@pytest.mark.parametrize(
    ("name", "namespace", "scopes"),
    [
        ("", "canopy/ana", {"read"}),
        ("agent", "Canopy Ana", {"read"}),
        ("agent", "canopy/ana", set()),
        ("agent", "canopy/ana", {"admin"}),
        ("a" * 65, "canopy/ana", {"read"}),
    ],
)
def test_a_token_needs_a_name_a_namespace_and_scopes(
    conn: Connection,
    name: str,
    namespace: str,
    scopes: set[str],
) -> None:
    with pytest.raises(accounts.InvalidError):
        accounts.mint(conn, person(PostgresTables(conn), "ana"), name, namespace, scopes)


def test_an_unknown_secret_gives_nothing(conn: Connection) -> None:
    assert accounts.token_scope(conn, "lvt_nope") is None
    assert accounts.session_account(conn, "nope") is None
