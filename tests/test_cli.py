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


def test_serve_without_local_db_exits_nonzero(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STARRYDATA_MCP_CACHE_DIR", str(tmp_path / "empty-cache"))
    result = runner.invoke(cli.app, ["serve"])
    assert result.exit_code == 1
    assert "ingest" in result.output
