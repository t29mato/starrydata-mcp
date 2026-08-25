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
from .infrastructure.ingestion.downloader import ChecksumMismatchError
from .infrastructure.ingestion.interrupt import cooperative_sigint
from .infrastructure.ingestion.pipeline import IngestAlreadyRunningError, run_ingest

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _parse_http_addr(addr: str) -> tuple[str, int]:
    """`":7860"` -> `("0.0.0.0", 7860)`; `"127.0.0.1:9000"` -> that pair;
    `"7860"` (bare port) -> `("0.0.0.0", 7860)`."""
    if ":" in addr:
        host, _, port_str = addr.rpartition(":")
        host = host or "0.0.0.0"
    else:
        host, port_str = "0.0.0.0", addr
    return host, int(port_str)


@app.command()
def ingest(
    force: bool = typer.Option(False, help="Rebuild even if the snapshot is unchanged."),
) -> None:
    """Download the latest public Starrydata snapshot and (re)build the local DuckDB file."""

    def announce_interrupt() -> None:
        typer.echo(
            "\nStopping as soon as it's safe to (after the current step)... "
            "press Ctrl+C again to quit immediately.",
            err=True,
        )

    try:
        with cooperative_sigint(on_first_press=announce_interrupt) as raise_if_interrupted:

            def on_progress(message: str) -> None:
                typer.echo(message)
                raise_if_interrupted()

            result = run_ingest(
                cache_dir=config.cache_dir(),
                db_path=config.db_path(),
                force=force,
                on_progress=on_progress,
            )
    except KeyboardInterrupt:
        # run_ingest already cleaned up any partial .tmp/.wal/staging files
        # before this propagates (see pipeline.py) — safe to just re-run.
        typer.echo(
            "\nInterrupted — partial files were cleaned up. "
            "Safe to run `starrydata-mcp ingest` again.",
            err=True,
        )
        raise typer.Exit(code=130) from None
    except IngestAlreadyRunningError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    except ChecksumMismatchError as exc:
        typer.echo(
            f"Error: download verification failed ({exc}). This usually means a "
            "network glitch mid-download — just try again.",
            err=True,
        )
        raise typer.Exit(code=1) from None

    if result.rebuilt:
        typer.echo(f"Rebuilt {result.db_path} from snapshot {result.db_snapshot}")
    else:
        typer.echo(f"Already up to date (snapshot {result.db_snapshot}); nothing to do.")


@app.command()
def serve(
    http: str | None = typer.Option(
        None,
        "--http",
        metavar="[HOST]:PORT",
        help=(
            'Serve over streamable-HTTP instead of stdio, e.g. "--http :7860" '
            "(all interfaces, port 7860 — the Hugging Face Spaces convention) or "
            '"--http 127.0.0.1:9000". Omit for stdio (default; for local clients '
            "like Claude Desktop/Code that spawn this process directly)."
        ),
    ),
) -> None:
    """Start the MCP server against the local DuckDB file (stdio by default).

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

    server = build_server(config.db_path())

    if http is None:
        server.run("stdio")
        return

    import uvicorn

    from .interface.rate_limit import RateLimitMiddleware

    host, port = _parse_http_addr(http)
    # stateless_http=True: no server-side session state between requests.
    # Right choice for a single-container public deployment (e.g. HF
    # Spaces) — no session affinity to worry about if the platform restarts
    # or fronts this with a load balancer later.
    asgi_app = RateLimitMiddleware(
        server.streamable_http_app(stateless_http=True),
        max_requests=config.rate_limit_max_requests(),
        window_seconds=config.rate_limit_window_seconds(),
    )
    typer.echo(
        f"Serving streamable-HTTP on http://{host}:{port} "
        "(MCP endpoint: /mcp, health check: /health)"
    )
    uvicorn.run(asgi_app, host=host, port=port, log_level="info")


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    # Trivial entrypoint boilerplate: only runs under `python -m
    # starrydata_mcp.cli`, never under a plain pytest import, so
    # coverage.py can't see it execute in-process. Exercised (functionally,
    # if not coverage-tracked) by
    # test_cli.py::test_running_as_main_module_invokes_the_typer_app, which
    # spawns it as a real subprocess.
    sys.exit(main())
