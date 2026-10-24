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


@cli.command()
def migrate() -> None:
    """Apply the database's migrations: the database DATABASE_URL names."""
    from louvre.core import db  # noqa: PLC0415  (only the commands that need the database import it)

    with db.connect(_database_url()) as conn:
        applied = db.migrate(conn)
    click.echo(f"applied {', '.join(applied)}" if applied else "the database is up to date")


@cli.command()
def demo() -> None:
    """Publish the demo's artifacts, unless they are published already."""
    from louvre.core import db  # noqa: PLC0415  (as above)
    from louvre.core import demo as demo_  # noqa: PLC0415
    from louvre.core.postgres import PostgresTables  # noqa: PLC0415

    with db.connect(_database_url()) as conn:
        db.migrate(conn)
        published = demo_.seed(PostgresTables(conn))
    click.echo(f"published the demo in {demo_.NAMESPACE}" if published else "the demo is published already")


def main() -> None:
    """Run the CLI as the `louvre` program, exiting with its status."""
    cli(prog_name="louvre")


def _database_url() -> str:
    from louvre.core import db  # noqa: PLC0415  (as above)

    try:
        return db.database_url()
    except db.NotConfiguredError as e:
        raise click.ClickException(str(e)) from None
