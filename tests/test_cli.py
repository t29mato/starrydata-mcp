import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from typer.testing import CliRunner

from starrydata_mcp import cli
from starrydata_mcp.infrastructure.ingestion.downloader import ChecksumMismatchError
from starrydata_mcp.infrastructure.ingestion.pipeline import (
    IngestAlreadyRunningError,
    IngestResult,
)

runner = CliRunner()


def test_ingest_reports_rebuild(monkeypatch, tmp_path: Path) -> None:
    def fake_run_ingest(
        *,
        cache_dir: Path,
        db_path: Path,
        force: bool = False,
        on_progress: Callable = lambda m: None,
    ) -> IngestResult:
        return IngestResult(rebuilt=True, db_snapshot="2026-08-15 02:00:02 JST", db_path=db_path)

    monkeypatch.setattr(cli, "run_ingest", fake_run_ingest)
    result = runner.invoke(cli.app, ["ingest"])
    assert result.exit_code == 0
    assert "Rebuilt" in result.output


def test_ingest_reports_skip(monkeypatch, tmp_path: Path) -> None:
    def fake_run_ingest(
        *,
        cache_dir: Path,
        db_path: Path,
        force: bool = False,
        on_progress: Callable = lambda m: None,
    ) -> IngestResult:
        return IngestResult(rebuilt=False, db_snapshot="2026-08-15 02:00:02 JST", db_path=db_path)

    monkeypatch.setattr(cli, "run_ingest", fake_run_ingest)
    result = runner.invoke(cli.app, ["ingest"])
    assert result.exit_code == 0
    assert "up to date" in result.output


def test_ingest_forwards_progress_messages_to_stdout(monkeypatch, tmp_path: Path) -> None:
    def fake_run_ingest(
        *,
        cache_dir: Path,
        db_path: Path,
        force: bool = False,
        on_progress: Callable = lambda m: None,
    ) -> IngestResult:
        on_progress("Downloading all_papers.csv.gz (9.5 MB)...")
        on_progress("Loading curves...")
        return IngestResult(rebuilt=True, db_snapshot="snap", db_path=db_path)

    monkeypatch.setattr(cli, "run_ingest", fake_run_ingest)
    result = runner.invoke(cli.app, ["ingest"])
    assert result.exit_code == 0
    assert "Downloading all_papers.csv.gz" in result.output
    assert "Loading curves..." in result.output


def test_ingest_keyboard_interrupt_gives_friendly_message_and_exit_130(
    monkeypatch, tmp_path: Path
) -> None:
    def fake_run_ingest(**_kwargs: object) -> IngestResult:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_ingest", fake_run_ingest)
    result = runner.invoke(cli.app, ["ingest"])
    assert result.exit_code == 130
    assert "Interrupted" in result.output
    assert "cleaned up" in result.output


def test_ingest_lock_conflict_gives_friendly_error_not_traceback(
    monkeypatch, tmp_path: Path
) -> None:
    def fake_run_ingest(**_kwargs: object) -> IngestResult:
        raise IngestAlreadyRunningError("4242")

    monkeypatch.setattr(cli, "run_ingest", fake_run_ingest)
    result = runner.invoke(cli.app, ["ingest"])
    assert result.exit_code == 1
    assert "4242" in result.output
    assert "already" in result.output.lower()


def test_ingest_checksum_mismatch_gives_friendly_error(monkeypatch, tmp_path: Path) -> None:
    def fake_run_ingest(**_kwargs: object) -> IngestResult:
        raise ChecksumMismatchError("all_curves.csv.gz", "aaa", "bbb")

    monkeypatch.setattr(cli, "run_ingest", fake_run_ingest)
    result = runner.invoke(cli.app, ["ingest"])
    assert result.exit_code == 1
    assert "verification failed" in result.output
    assert "try again" in result.output


def test_ingest_real_sigint_announces_before_stopping(monkeypatch, tmp_path: Path) -> None:
    # Unlike test_ingest_keyboard_interrupt_gives_friendly_message_and_exit_130
    # (which raises KeyboardInterrupt directly from the fake), this goes
    # through cli.py's *real* cooperative_sigint context manager — a real
    # SIGINT delivered mid-run must trigger the "Stopping..." announcement
    # (announce_interrupt) before the next on_progress checkpoint raises.
    def fake_run_ingest(
        *,
        cache_dir: Path,
        db_path: Path,
        force: bool = False,
        on_progress: Callable = lambda m: None,
    ) -> IngestResult:
        on_progress("Downloading...")
        signal.raise_signal(signal.SIGINT)  # simulate a real Ctrl+C, in-process
        on_progress("Loading papers...")  # next checkpoint notices and raises
        return IngestResult(rebuilt=True, db_snapshot="snap", db_path=db_path)

    monkeypatch.setattr(cli, "run_ingest", fake_run_ingest)
    result = runner.invoke(cli.app, ["ingest"])
    assert result.exit_code == 130
    assert "Stopping as soon as it's safe" in result.output
    assert "Interrupted" in result.output


def test_serve_without_local_db_exits_nonzero(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STARRYDATA_MCP_CACHE_DIR", str(tmp_path / "empty-cache"))
    result = runner.invoke(cli.app, ["serve"])
    assert result.exit_code == 1
    assert "ingest" in result.output


def test_serve_wires_build_server_and_runs_stdio(monkeypatch, tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    db_path = cache_dir / "starrydata.duckdb"
    db_path.write_bytes(b"")  # serve() only checks that this path exists
    monkeypatch.setenv("STARRYDATA_MCP_CACHE_DIR", str(cache_dir))

    calls: dict[str, object] = {}

    class FakeServer:
        def run(self, transport: str) -> None:
            calls["transport"] = transport

    def fake_build_server(path: Path) -> FakeServer:
        calls["path"] = path
        return FakeServer()

    monkeypatch.setattr("starrydata_mcp.interface.mcp_server.build_server", fake_build_server)

    result = runner.invoke(cli.app, ["serve"])
    assert result.exit_code == 0
    assert calls["path"] == db_path
    assert calls["transport"] == "stdio"


def test_parse_http_addr_bare_colon_port() -> None:
    assert cli._parse_http_addr(":7860") == ("0.0.0.0", 7860)


def test_parse_http_addr_explicit_host() -> None:
    assert cli._parse_http_addr("127.0.0.1:9000") == ("127.0.0.1", 9000)


def test_parse_http_addr_bare_port_defaults_host() -> None:
    assert cli._parse_http_addr("7860") == ("0.0.0.0", 7860)


def test_serve_http_wires_rate_limited_streamable_http_app_into_uvicorn(
    monkeypatch, tmp_path: Path
) -> None:
    import uvicorn

    from starrydata_mcp.interface.rate_limit import RateLimitMiddleware

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    db_path = cache_dir / "starrydata.duckdb"
    db_path.write_bytes(b"")
    monkeypatch.setenv("STARRYDATA_MCP_CACHE_DIR", str(cache_dir))

    sentinel_app = object()

    class FakeServer:
        def streamable_http_app(self, **kwargs: object) -> object:
            return sentinel_app

    monkeypatch.setattr(
        "starrydata_mcp.interface.mcp_server.build_server", lambda path: FakeServer()
    )

    calls: dict[str, object] = {}
    monkeypatch.setattr(
        uvicorn,
        "run",
        lambda app, **kwargs: calls.update(app=app, **kwargs),
    )

    result = runner.invoke(cli.app, ["serve", "--http", "127.0.0.1:9001"])
    assert result.exit_code == 0
    assert calls["host"] == "127.0.0.1"
    assert calls["port"] == 9001
    assert isinstance(calls["app"], RateLimitMiddleware)
    assert calls["app"]._app is sentinel_app  # the fake server's app, not double-wrapped
    assert "9001" in result.output


def test_running_as_main_module_invokes_the_typer_app() -> None:
    # Covers `def main()` and the `if __name__ == "__main__"` guard, which
    # only run when the module is executed directly (`python -m ...`) —
    # never via a plain pytest import. Also doubles as a smoke test that the
    # packaged entrypoint actually starts up without import errors.
    result = subprocess.run(
        [sys.executable, "-m", "starrydata_mcp.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "ingest" in result.stdout
    assert "serve" in result.stdout
