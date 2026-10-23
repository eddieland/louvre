"""The `louvre` console script: the root command, which every subcommand is added to."""

import click


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="louvre", message="%(prog)s %(version)s")
def cli() -> None:
    """Run louvre's commands."""


def main() -> None:
    """Run the CLI as the `louvre` program, exiting with its status."""
    cli(prog_name="louvre")
