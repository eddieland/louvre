import os
from importlib.metadata import version
from unittest import mock

import uvicorn
from click.testing import CliRunner
from fastapi import FastAPI

from louvre.cli.main import cli
from louvre.core.db import Connection


def test_version_prints_the_installed_version(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--version"], prog_name="louvre")

    assert result.exit_code == 0
    assert result.stdout == f"louvre {version('louvre')}\n"


def test_help_names_the_program(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["-h"], prog_name="louvre")

    assert result.exit_code == 0
    assert result.stdout.startswith("Usage: louvre [OPTIONS] COMMAND [ARGS]...")


def test_serve_runs_the_web_app(runner: CliRunner) -> None:
    with mock.patch.object(uvicorn, "run", autospec=True) as run:
        result = runner.invoke(cli, ["serve", "--port", "9001"], prog_name="louvre")

    assert result.exit_code == 0
    (app,), options = run.call_args
    assert isinstance(app, FastAPI)
    assert options == {"host": "127.0.0.1", "port": 9001}


def test_migrate_and_demo_need_a_database(runner: CliRunner) -> None:
    with mock.patch.dict(os.environ, {"DATABASE_URL": "", "POSTGRES_URL": ""}):
        result = runner.invoke(cli, ["migrate"], prog_name="louvre")

    assert result.exit_code == 1
    assert "set DATABASE_URL or POSTGRES_URL" in result.stderr


def test_demo_publishes_once(runner: CliRunner, database_url: str, conn: Connection) -> None:
    with mock.patch.dict(os.environ, {"DATABASE_URL": database_url}):
        first = runner.invoke(cli, ["demo"], prog_name="louvre")
        again = runner.invoke(cli, ["demo"], prog_name="louvre")
        migrated = runner.invoke(cli, ["migrate"], prog_name="louvre")

    assert first.stdout == "published the demo in demo\n"
    assert again.stdout == "the demo is published already\n"
    assert migrated.stdout == "the database is up to date\n"
    row = conn.execute("SELECT count(*) AS n FROM artifacts WHERE namespace = 'demo'").fetchone()
    assert row == {"n": 8}
