"""Who a request is from, and the store it reaches: the dependencies every route of the API and the content shares.

A signed-in person is named by the session cookie and reads every namespace. Without one, a request reads the demo's
namespace when the demo is on, and nothing otherwise. The database is opened once a request, and migrated, with the
demo seeded, the first time this process opens it. A deployment with no database serves the demo from this process's
memory instead, seeded the first time it is asked for: everyone reads it, and nobody signs in, since people, sessions,
and tokens are rows of the database.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from louvre.core import accounts, db, demo
from louvre.core.accounts import Account
from louvre.core.memory import MemoryTables
from louvre.core.postgres import PostgresTables
from louvre.core.store import Store
from louvre.core.tables import Tables
from louvre.web.settings import Settings

#: The cookie a session's secret is kept in.
SESSION_COOKIE = "louvre_session"
#: What a request that needs the database is told when none is named.
NOT_CONFIGURED = "No database is configured: set DATABASE_URL (docs/DEPLOY.md)."


@dataclass(frozen=True)
class Opened:
    """What a request has open: the store's tables, and the database's connection when there is one."""

    tables: Tables
    #: None without a database: then nothing that needs one, sign-in and tokens among it, can be served.
    conn: db.Connection | None


class Database:
    """The app's data: the database its settings name, or the demo in memory, and whether this process set it up."""

    def __init__(self, settings: Settings) -> None:
        """Serve the database `settings` names, with the demo when they turn it on, or the demo alone without one."""
        self.settings = settings
        self._ready = False
        self._memory: MemoryTables | None = None
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        """Whether a database is named at all."""
        return self.settings.database_url is not None

    @property
    def demo(self) -> bool:
        """Whether the demo is served: when the settings turn it on, and always without a database.

        Without one, the demo is all there is to read.
        """
        return self.settings.demo or not self.configured

    @contextmanager
    def opened(self) -> Iterator[Opened]:
        """Open the tables: a connection to the database, migrated first if this process has not, or the memory.

        Yields:
            The tables, and the connection when there is a database, closed when the block ends.
        """
        url = self.settings.database_url
        if url is None:
            yield Opened(self._memory_tables(), None)
            return
        with db.connect(url) as conn:
            tables = PostgresTables(conn)
            self._prepare(conn, tables)
            yield Opened(tables, conn)

    def _prepare(self, conn: db.Connection, tables: Tables) -> None:
        with self._lock:
            if self._ready:
                return
            db.migrate(conn)
            if self.settings.demo:
                demo.seed(tables, base_url=self.settings.base_url)
            self._ready = True

    def _memory_tables(self) -> MemoryTables:
        with self._lock:
            if self._memory is None:
                made = MemoryTables()
                demo.seed(made, base_url=self.settings.base_url)
                self._memory = made
            return self._memory


def database(request: Request) -> Database:
    """Find the app's database.

    Returns:
        It.
    """
    found = request.app.state.database
    assert isinstance(found, Database)  # noqa: S101  (create() sets it)
    return found


def opened(found: Annotated[Database, Depends(database)]) -> Iterator[Opened]:
    """Open the request's tables, and its connection when there is a database.

    Yields:
        Them.
    """
    with found.opened() as held:
        yield held


#: What the request has open, as a route takes it.
type Held = Annotated[Opened, Depends(opened)]


def connection(held: Held) -> db.Connection:
    """Require the request's connection, for a route that reads people, sessions, or tokens.

    Returns:
        The connection.

    Raises:
        HTTPException: 503, `not_configured`, when no database is named.
    """
    if held.conn is None:
        raise HTTPException(status_code=503, detail={"code": "not_configured", "message": NOT_CONFIGURED})
    return held.conn


#: The request's connection, as a route takes it.
type Conn = Annotated[db.Connection, Depends(connection)]


def viewer(request: Request, held: Held) -> Account | None:
    """Find who is signed in.

    Returns:
        Their account, or None for nobody, as everyone is without a database.
    """
    secret = request.cookies.get(SESSION_COOKIE)
    return None if not secret or held.conn is None else accounts.session_account(held.conn, secret)


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


def reader(request: Request, held: Held, account: Viewer, found: Annotated[Database, Depends(database)]) -> Store:
    """Make the store the request reaches: as its person, or as an anonymous reader of the demo.

    Returns:
        The store.

    Raises:
        HTTPException: 401, `unauthenticated`, for nobody when the demo is off.
    """
    base_url = found.settings.base_url or str(request.base_url).rstrip("/")
    if account is not None:
        return Store(held.tables, accounts.person_scope(account), base_url=base_url)
    if found.demo:
        return Store(held.tables, accounts.reader_scope({demo.NAMESPACE}), base_url=base_url)
    raise HTTPException(status_code=401, detail={"code": "unauthenticated", "message": "Sign in to read artifacts."})


#: The request's store.
type Reader = Annotated[Store, Depends(reader)]
