from importlib.metadata import version

from click.testing import CliRunner

from louvre.cli.main import cli


def test_version_prints_the_installed_version(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--version"], prog_name="louvre")

    assert result.exit_code == 0
    assert result.stdout == f"louvre {version('louvre')}\n"


def test_help_names_the_program(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["-h"], prog_name="louvre")

    assert result.exit_code == 0
    assert result.stdout.startswith("Usage: louvre [OPTIONS] COMMAND [ARGS]...")
