"""Shared fixtures, for every test module.

The store's tests run against a real Postgres, named by `LOUVRE_TEST_DATABASE_URL` (a database the tests may create
others beside, such as `postgresql://louvre@127.0.0.1:5432/postgres`). Each pytest worker gets a database of its own,
migrated once, and every test starts from empty tables. Without the variable, those tests are skipped, except in CI,
where they fail: CI must never pass by skipping them. The store's contract is held on the in-memory tables too: a
test that takes `tables` runs once on each.
"""

import dataclasses
import os
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import ExitStack

import psycopg
import pytest
import uvicorn
from click.testing import CliRunner
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, sync_playwright
from psycopg import conninfo, sql

from louvre.core import db
from louvre.core.accounts import Account
from louvre.core.memory import MemoryTables
from louvre.core.postgres import PostgresTables
from louvre.core.store import Author, Permission, Scope, Store, Via
from louvre.core.tables import Tables
from louvre.web.app import create
from louvre.web.settings import Settings

#: The variable that names the Postgres the tests use.
TEST_DATABASE = "LOUVRE_TEST_DATABASE_URL"
#: Where Louvre's pages are, in the tests' stores and apps.
BASE_URL = "https://louvre.test"
#: How long the live app may take to start or stop, in seconds.
LIVE_DEADLINE = 15.0
#: The header every write to the web app carries.
WRITES = {"X-Louvre": "1"}
#: Every table the store writes, emptied before each test.
TABLES = ("changes", "comments", "threads", "versions", "artifacts", "authors", "tokens", "sessions", "accounts")


@pytest.fixture
def runner() -> CliRunner:
    """A runner for louvre's commands, in this process, with stdout and stderr kept apart."""
    return CliRunner()


@pytest.fixture(scope="session")
def database_url(request: pytest.FixtureRequest) -> Iterator[str]:
    """A migrated database of this worker's own, made fresh for the session and dropped after it."""
    admin = os.environ.get(TEST_DATABASE)
    if not admin:
        if os.environ.get("CI"):
            pytest.fail(f"{TEST_DATABASE} is not set in CI: the store's tests would not run")
        pytest.skip(f"set {TEST_DATABASE} to run the tests that need Postgres")
    worker = getattr(request.config, "workerinput", {}).get("workerid", "main")
    name = f"louvre_test_{worker}"
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = conninfo.make_conninfo(admin, dbname=name)
    with db.connect(url) as conn:
        db.migrate(conn)
    yield url
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def conn(database_url: str) -> Iterator[db.Connection]:
    """A connection to the test database, its tables emptied first."""
    with db.connect(database_url) as connection:
        empty(connection)
        yield connection


def empty(connection: db.Connection) -> None:
    """Empty every table the store writes."""
    connection.execute(
        sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(sql.SQL(", ").join(sql.Identifier(t) for t in TABLES)),
    )


@pytest.fixture
def postgres(conn: db.Connection) -> PostgresTables:
    """The store's tables in the test database, emptied first."""
    return PostgresTables(conn)


@pytest.fixture(params=["postgres", "memory"])
def tables(request: pytest.FixtureRequest) -> Tables:
    """The store's tables, in Postgres and then in memory: a test that takes them holds both to the contract."""
    if request.param == "postgres":
        found = request.getfixturevalue("postgres")
        assert isinstance(found, PostgresTables)
        return found
    return MemoryTables()


def person(tables: Tables, login: str, name: str | None = None) -> Account:
    """Record a person who signed in with the dev sign-in, as `dev:LOGIN`.

    Returns:
        Their account.
    """
    account = Account(f"dev:{login}", login, name or login.title())
    tables.upsert_account(account.id, account.login, account.display_name)
    return account


def agent_of(
    tables: Tables,
    namespace: str = "canopy/sam",
    scopes: tuple[str, ...] = ("read", "publish", "comment"),
) -> Store:
    """Make a store as an agent of Sam's, the scope a token of `scopes` in `namespace` gives (accounts.token_scope).

    Returns:
        The store.
    """
    sam = person(tables, "sam", "Sam Okafor")
    scope = Scope(
        author=Author(f"agent:{sam.id}:canopy worker", "canopy worker", "agent", sam.id),
        via=Via.MCP,
        namespaces=frozenset({namespace}),
        home=namespace,
        permissions=frozenset(Permission(s) for s in scopes),
        account_id=sam.id,
    )
    return Store(tables, scope, base_url=BASE_URL)


#: Makes a store as an agent of Sam's with `scopes` in `namespace`, on the tables under test.
type MakeAgent = Callable[..., Store]


@pytest.fixture
def agent(tables: Tables) -> MakeAgent:
    """Make a store as an agent of Sam's, with `scopes` in `namespace`, on the tables under test."""

    def make(namespace: str = "canopy/sam", scopes: tuple[str, ...] = ("read", "publish", "comment")) -> Store:
        return agent_of(tables, namespace, scopes)

    return make


#: Makes a client of the web app, configured by `Settings` with the fields given changed.
type MakeWeb = Callable[..., TestClient]


@pytest.fixture
def web(database_url: str, conn: db.Connection) -> Iterator[MakeWeb]:
    """Make clients of the web app on the test database, with sign-in by name on, and the demo off unless asked."""
    with ExitStack() as stack:

        def make(**changes: object) -> TestClient:
            settings = dataclasses.replace(web_settings(database_url), **changes)  # type: ignore[arg-type]
            return stack.enter_context(TestClient(create(settings), base_url=BASE_URL))

        yield make


def web_settings(database_url: str | None) -> Settings:
    """Configure the web app for a test: on `database_url`, with GitHub and sign-in by name on, and the demo off.

    Returns:
        The settings.
    """
    return Settings(
        database_url=database_url,
        base_url=BASE_URL,
        github_client_id="client-id",
        github_client_secret="client-secret",  # noqa: S106  (a test's)
        allowed_logins=frozenset({"ana"}),
        dev_sign_in=True,
        demo=False,
        secure_cookies=False,
    )


def sign_in(client: TestClient, login: str, name: str | None = None) -> None:
    """Sign in as `login` by name, as the web UI does."""
    response = client.post("/auth/dev", json={"login": login, "name": name}, headers=WRITES)
    assert response.status_code == 204, response.text


@pytest.fixture(scope="module")
def live_app(database_url: str) -> Iterator[str]:
    """The web app on an emptied test database, with the demo and sign-in by name, served on a free port."""
    with db.connect(database_url) as connection:
        empty(connection)
    settings = dataclasses.replace(web_settings(database_url), demo=True, base_url="")
    server = uvicorn.Server(uvicorn.Config(create(settings), host="127.0.0.1", port=0, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + LIVE_DEADLINE
    while not server.started:
        assert time.monotonic() < deadline, "the web app did not start"
        time.sleep(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(LIVE_DEADLINE)


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    """Chromium, driven by Playwright."""
    with sync_playwright() as playwright:
        # A Chromium of the machine's, where Playwright's own download is not to be had.
        executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE") or None
        launched = playwright.chromium.launch(executable_path=executable)
        yield launched
        launched.close()
