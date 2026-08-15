"""Composition root / CLI entrypoint (`starrydata-mcp ingest|serve`).

Deliberately outside the domain/application/infrastructure/interface
layering (docs/design/architecture.md §4): this is where those layers get
wired together, which is exactly the one place clean architecture expects
concrete infrastructure and interface classes to meet.
"""

from __future__ import annotations

import sys

import typer

from . import config
from .infrastructure.ingestion.pipeline import run_ingest

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def ingest(
    force: bool = typer.Option(False, help="Rebuild even if the snapshot is unchanged."),
) -> None:
    """Download the latest public Starrydata snapshot and (re)build the local DuckDB file."""
    result = run_ingest(cache_dir=config.cache_dir(), db_path=config.db_path(), force=force)
    if result.rebuilt:
        typer.echo(f"Rebuilt {result.db_path} from snapshot {result.db_snapshot}")
    else:
        typer.echo(f"Already up to date (snapshot {result.db_snapshot}); nothing to do.")


@app.command()
def serve() -> None:
    """Start the MCP server (stdio) against the local DuckDB file.

    Run `starrydata-mcp ingest` first if `~/.cache/starrydata-mcp/starrydata.duckdb`
    doesn't exist yet.
    """
    if not config.db_path().exists():
        typer.echo(
            f"No local database at {config.db_path()}. Run `starrydata-mcp ingest` first.",
            err=True,
        )
        raise typer.Exit(code=1)

    from .interface.mcp_server import build_server

    build_server(config.db_path()).run("stdio")


def main() -> None:
    app()


if __name__ == "__main__":
    sys.exit(main())
