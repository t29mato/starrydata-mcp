from pathlib import Path

from typer.testing import CliRunner

from starrydata_mcp import cli
from starrydata_mcp.infrastructure.ingestion.pipeline import IngestResult

runner = CliRunner()


def test_ingest_reports_rebuild(monkeypatch, tmp_path: Path) -> None:
    def fake_run_ingest(*, cache_dir: Path, db_path: Path, force: bool = False) -> IngestResult:
        return IngestResult(rebuilt=True, db_snapshot="2026-08-15 02:00:02 JST", db_path=db_path)

    monkeypatch.setattr(cli, "run_ingest", fake_run_ingest)
    result = runner.invoke(cli.app, ["ingest"])
    assert result.exit_code == 0
    assert "Rebuilt" in result.output


def test_ingest_reports_skip(monkeypatch, tmp_path: Path) -> None:
    def fake_run_ingest(*, cache_dir: Path, db_path: Path, force: bool = False) -> IngestResult:
        return IngestResult(rebuilt=False, db_snapshot="2026-08-15 02:00:02 JST", db_path=db_path)

    monkeypatch.setattr(cli, "run_ingest", fake_run_ingest)
    result = runner.invoke(cli.app, ["ingest"])
    assert result.exit_code == 0
    assert "up to date" in result.output


def test_serve_without_local_db_exits_nonzero(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STARRYDATA_MCP_CACHE_DIR", str(tmp_path / "empty-cache"))
    result = runner.invoke(cli.app, ["serve"])
    assert result.exit_code == 1
    assert "ingest" in result.output
