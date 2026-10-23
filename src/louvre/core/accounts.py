"""People, the sessions they sign in with, and the tokens they mint for agents (REQUIREMENTS L4, L5).

A session or token is a random secret handed out once; only its sha256 is kept, so the database never holds one that
works. A token is bound to the person who minted it and to one namespace, with scopes, and becomes the store's scope
for every call made with it: an agent's comment is `kind: agent`, on its person's behalf.
"""

import hashlib
import re
import secrets
from collections.abc import Iterable, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from louvre.core.db import Connection
from louvre.core.store import Author, Permission, Scope, Via

#: How long a session lasts after sign-in.
SESSION_DAYS = 30
#: How a token's secret starts, so one is recognized in a config file or a leak scan.
TOKEN_PREFIX = "lvt_"  # noqa: S105  (a prefix, not a secret)
#: A namespace: lowercase words joined by `.`, `-`, `_`, or `/`, such as `canopy/eddie`.
NAMESPACE = re.compile(r"^[a-z0-9](?:[a-z0-9._/-]{0,62}[a-z0-9])?$")
#: An agent's name, as its comments show it.
AGENT_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9 ._-]{0,62}[A-Za-z0-9])?$")
#: What a signed-in person may do: read every namespace, and comment on the web.
PERSON_PERMISSIONS = frozenset({Permission.READ, Permission.COMMENT})


@dataclass(frozen=True)
class Account:
    """A person who signs in."""

    #: Stable for the life of the account: the identity provider's id, such as `gh:583231`.
    id: str
    #: Their handle at the provider, such as a GitHub login.
    login: str
    display_name: str


@dataclass(frozen=True)
class Token:
    """A token a person minted for an agent, as its page lists it: never its secret."""

    id: str
    #: The agent's name, as its comments show it.
    name: str
    #: The one namespace it reads and writes.
    namespace: str
    scopes: AbstractSet[Permission]
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class InvalidError(ValueError):
    """A token's name, namespace, or scopes cannot be used."""


def upsert_account(conn: Connection, account: Account) -> Account:
    """Record a person as their provider names them now.

    Returns:
        The account.
    """
    conn.execute(
        "INSERT INTO accounts (id, login, display_name) VALUES (%s, %s, %s)"
        " ON CONFLICT (id) DO UPDATE SET login = excluded.login, display_name = excluded.display_name",
        (account.id, account.login, account.display_name),
    )
    return account


def names(conn: Connection, account_ids: Iterable[str]) -> dict[str, str]:
    """Find people's names by their account ids.

    Returns:
        Each id found, with its person's name.
    """
    rows = conn.execute(
        "SELECT id, display_name FROM accounts WHERE id = ANY(%s)",
        (sorted(set(account_ids)),),
    ).fetchall()
    return {str(row["id"]): str(row["display_name"]) for row in rows}


def start_session(conn: Connection, account_id: str) -> str:
    """Sign a person in.

    Returns:
        The session's secret, for its cookie.
    """
    secret = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token_hash, account_id, expires_at) VALUES (%s, %s, %s)",
        (_hash(secret), account_id, datetime.now(UTC) + timedelta(days=SESSION_DAYS)),
    )
    return secret


def session_account(conn: Connection, secret: str) -> Account | None:
    """Find who a session's secret signs in.

    Returns:
        The account, or None for no session, or one expired.
    """
    row = conn.execute(
        "SELECT a.* FROM sessions s JOIN accounts a ON a.id = s.account_id"
        " WHERE s.token_hash = %s AND s.expires_at > now()",
        (_hash(secret),),
    ).fetchone()
    return None if row is None else _account(row)


def end_session(conn: Connection, secret: str) -> None:
    """Sign a session out."""
    conn.execute("DELETE FROM sessions WHERE token_hash = %s", (_hash(secret),))


def mint(conn: Connection, account: Account, name: str, namespace: str, scopes: AbstractSet[str]) -> tuple[Token, str]:
    """Mint a token for an agent of `account`'s, bound to `namespace` with `scopes`.

    Returns:
        The token, and its secret, which is shown this once.

    Raises:
        InvalidError: The name, namespace, or scopes cannot be used.
    """
    name = name.strip()
    if not AGENT_NAME.match(name):
        raise InvalidError("an agent's name is 1 to 64 letters, digits, spaces, dots, dashes, or underscores")
    if not NAMESPACE.match(namespace):
        raise InvalidError("a namespace is lowercase letters, digits, and . _ - /, such as canopy/you")
    try:
        permissions = sorted(Permission(scope) for scope in scopes)
    except ValueError:
        raise InvalidError("scopes are read, publish, and comment") from None
    if not permissions:
        raise InvalidError("a token needs at least one scope")
    secret = TOKEN_PREFIX + secrets.token_urlsafe(32)
    token_id = f"tok_{secrets.token_hex(6)}"
    row = conn.execute(
        "INSERT INTO tokens (id, secret_hash, account_id, name, namespace, scopes) VALUES (%s, %s, %s, %s, %s, %s)"
        " RETURNING *",
        (token_id, _hash(secret), account.id, name, namespace, [p.value for p in permissions]),
    ).fetchone()
    assert row is not None  # noqa: S101  (an INSERT ... RETURNING returns its row)
    return _token(row), secret


def tokens(conn: Connection, account: Account) -> Sequence[Token]:
    """List a person's tokens, newest first, revoked ones too.

    Returns:
        The tokens.
    """
    rows = conn.execute(
        "SELECT * FROM tokens WHERE account_id = %s ORDER BY created_at DESC, id",
        (account.id,),
    ).fetchall()
    return [_token(row) for row in rows]


def revoke(conn: Connection, account: Account, token_id: str) -> bool:
    """Revoke one of a person's tokens: every call with it is refused from now on.

    Returns:
        Whether a token of theirs was revoked now.
    """
    done = conn.execute(
        "UPDATE tokens SET revoked_at = now() WHERE id = %s AND account_id = %s AND revoked_at IS NULL",
        (token_id, account.id),
    )
    return done.rowcount == 1


def token_scope(conn: Connection, secret: str) -> Scope | None:
    """Find the scope a token's secret gives, and note that it was used.

    Returns:
        The scope: its agent writes on its person's behalf, in its namespace, with its scopes. None for no such
        token, or one revoked.
    """
    row = conn.execute(
        "UPDATE tokens t SET last_used_at = now() FROM accounts a WHERE t.secret_hash = %s AND t.revoked_at IS NULL"
        " AND a.id = t.account_id RETURNING t.*, a.login, a.display_name AS account_name",
        (_hash(secret),),
    ).fetchone()
    if row is None:
        return None
    account_id, name, namespace = str(row["account_id"]), str(row["name"]), str(row["namespace"])
    return Scope(
        author=Author(f"agent:{account_id}:{name}", name, "agent", account_id),
        via=Via.MCP,
        namespaces=frozenset({namespace}),
        home=namespace,
        permissions=frozenset(Permission(str(s)) for s in _list(row["scopes"])),
        account_id=account_id,
    )


def person_scope(account: Account) -> Scope:
    """Make the scope a signed-in person reads and comments in: every namespace, on the web.

    Returns:
        The scope.
    """
    return Scope(
        author=Author(account.id, account.display_name, "person"),
        via=Via.WEB,
        namespaces=None,
        home=None,
        permissions=PERSON_PERMISSIONS,
        account_id=account.id,
    )


def reader_scope(namespaces: AbstractSet[str]) -> Scope:
    """Make the scope of a reader who has not signed in: the public demo's namespaces, read only.

    Returns:
        The scope.
    """
    return Scope(
        author=Author("anonymous", "Anonymous", "person"),
        via=Via.WEB,
        namespaces=frozenset(namespaces),
        home=None,
        permissions=frozenset({Permission.READ}),
    )


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _list(value: object) -> list[object]:
    return [*value] if isinstance(value, list) else []


def _account(row: dict[str, object]) -> Account:
    return Account(str(row["id"]), str(row["login"]), str(row["display_name"]))


def _token(row: dict[str, object]) -> Token:
    def when(value: object) -> datetime | None:
        return value if isinstance(value, datetime) else None

    created = when(row["created_at"])
    assert created is not None  # noqa: S101  (the column is NOT NULL)
    return Token(
        id=str(row["id"]),
        name=str(row["name"]),
        namespace=str(row["namespace"]),
        scopes=frozenset(Permission(str(s)) for s in _list(row["scopes"])),
        created_at=created,
        last_used_at=when(row["last_used_at"]),
        revoked_at=when(row["revoked_at"]),
    )
