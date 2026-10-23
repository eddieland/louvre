"""The `louvre` console script: the root command, which every subcommand is added to."""

import click


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="louvre", message="%(prog)s %(version)s")
def cli() -> None:
    """Run louvre's commands."""


@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="The address to listen on.")
@click.option("--port", default=8000, show_default=True, help="The port to listen on.")
def serve(host: str, port: int) -> None:
    """Serve the web app, as the preview deployment does."""
    # Imported here: only this command needs the web app and its server.
    import uvicorn  # noqa: PLC0415

    from louvre.web.app import create  # noqa: PLC0415

    uvicorn.run(create(), host=host, port=port)


def main() -> None:
    """Run the CLI as the `louvre` program, exiting with its status."""
    cli(prog_name="louvre")
