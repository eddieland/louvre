"""Who a request is from, and the store it reaches: the dependencies every route of the API and the content shares.

A signed-in person is named by the session cookie and reads every namespace. Without one, a request reads the demo's
namespace when the demo is on, and nothing otherwise. The database is opened once a request, and migrated, with the
demo seeded, the first time this process opens it.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from louvre.core import accounts, db, demo
from louvre.core.accounts import Account
from louvre.core.store import Store
from louvre.web.settings import Settings

#: The cookie a session's secret is kept in.
SESSION_COOKIE = "louvre_session"
#: What a request that needs the database is told when none is named.
NOT_CONFIGURED = "No database is configured: set DATABASE_URL (docs/DEPLOY.md)."


class Database:
    """The app's database: where it is, and whether this process has migrated it yet."""

    def __init__(self, settings: Settings) -> None:
        """Serve the database `settings` names, with the demo when they turn it on."""
        self.settings = settings
        self._ready = False
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        """Whether a database is named at all."""
        return self.settings.database_url is not None

    @contextmanager
    def opened(self) -> Iterator[db.Connection]:
        """Open a connection, migrating the database first if this process has not.

        Yields:
            The connection, closed when the block ends.

        Raises:
            HTTPException: 503, `not_configured`, when no database is named.
        """
        url = self.settings.database_url
        if url is None:
            raise HTTPException(status_code=503, detail={"code": "not_configured", "message": NOT_CONFIGURED})
        with db.connect(url) as conn:
            self._prepare(conn)
            yield conn

    def _prepare(self, conn: db.Connection) -> None:
        with self._lock:
            if self._ready:
                return
            db.migrate(conn)
            if self.settings.demo:
                demo.seed(conn, base_url=self.settings.base_url)
            self._ready = True


def database(request: Request) -> Database:
    """Find the app's database.

    Returns:
        It.
    """
    found = request.app.state.database
    assert isinstance(found, Database)  # noqa: S101  (create() sets it)
    return found


def connection(found: Annotated[Database, Depends(database)]) -> Iterator[db.Connection]:
    """Open the request's connection.

    Yields:
        The connection.
    """
    with found.opened() as conn:
        yield conn


#: The request's connection, as a route takes it.
type Conn = Annotated[db.Connection, Depends(connection)]


def viewer(request: Request, conn: Conn) -> Account | None:
    """Find who is signed in.

    Returns:
        Their account, or None for nobody.
    """
    secret = request.cookies.get(SESSION_COOKIE)
    return None if not secret else accounts.session_account(conn, secret)


#: Who is signed in, if anyone.
type Viewer = Annotated[Account | None, Depends(viewer)]


def signed_in(account: Viewer) -> Account:
    """Require a signed-in person.

    Returns:
        Their account.

    Raises:
        HTTPException: 401, `unauthenticated`, for nobody.
    """
    if account is None:
        raise HTTPException(status_code=401, detail={"code": "unauthenticated", "message": "Sign in first."})
    return account


#: The signed-in person, required.
type Person = Annotated[Account, Depends(signed_in)]


def reader(request: Request, conn: Conn, account: Viewer, found: Annotated[Database, Depends(database)]) -> Store:
    """Make the store the request reaches: as its person, or as an anonymous reader of the demo.

    Returns:
        The store.

    Raises:
        HTTPException: 401, `unauthenticated`, for nobody when the demo is off.
    """
    settings = found.settings
    base_url = settings.base_url or str(request.base_url).rstrip("/")
    if account is not None:
        return Store(conn, accounts.person_scope(account), base_url=base_url)
    if settings.demo:
        return Store(conn, accounts.reader_scope({demo.NAMESPACE}), base_url=base_url)
    raise HTTPException(status_code=401, detail={"code": "unauthenticated", "message": "Sign in to read artifacts."})


#: The request's store.
type Reader = Annotated[Store, Depends(reader)]
