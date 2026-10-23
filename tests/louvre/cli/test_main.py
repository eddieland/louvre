from importlib.metadata import version
from unittest import mock

import uvicorn
from click.testing import CliRunner
from fastapi import FastAPI

from louvre.cli.main import cli


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
