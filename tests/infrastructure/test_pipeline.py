from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import duckdb
import httpx
import respx

from starrydata_mcp.infrastructure.ingestion.downloader import MANIFEST_URL, RELEASE_BASE_URL
from starrydata_mcp.infrastructure.ingestion.pipeline import _parse_db_snapshot, run_ingest

FIXTURES = Path(__file__).parent.parent / "fixtures" / "raw"


def _mock_manifest_and_files(db_snapshot: str) -> None:
    files = {
        "papers": (FIXTURES / "papers.csv").read_bytes(),
        "samples": (FIXTURES / "samples.csv").read_bytes(),
        "curves": (FIXTURES / "curves.csv").read_bytes(),
    }
    manifest_payload = {
        "generated_at": "2026-08-15T02:00:00+00:00",
        "db_snapshot": db_snapshot,
        "totals": {"papers": 2, "figures": 3, "samples": 3, "curves": 3},
        "all_data": {
            kind: {
                "filename": f"all_{kind}.csv.gz",
                "rows": 1,
                "bytes": len(content),
                "sha256": hashlib.sha256(gzip.compress(content)).hexdigest(),
            }
            for kind, content in files.items()
        },
    }
    respx.get(MANIFEST_URL).mock(return_value=httpx.Response(200, json=manifest_payload))
    for kind, content in files.items():
        respx.get(f"{RELEASE_BASE_URL}/all_{kind}.csv.gz").mock(
            return_value=httpx.Response(200, content=gzip.compress(content))
        )


@respx.mock
def test_first_run_builds_database(tmp_path: Path) -> None:
    _mock_manifest_and_files("2026-08-15 02:00:02 UTC+0900 (JST)")
    result = run_ingest(cache_dir=tmp_path / "cache", db_path=tmp_path / "starrydata.duckdb")
    assert result.rebuilt is True
    assert result.db_path.exists()

    con = duckdb.connect(str(result.db_path), read_only=True)
    assert con.execute("SELECT count(*) FROM papers").fetchone() == (2,)
    con.close()


@respx.mock
def test_second_run_with_unchanged_snapshot_is_skipped(tmp_path: Path) -> None:
    _mock_manifest_and_files("2026-08-15 02:00:02 UTC+0900 (JST)")
    cache_dir, db_path = tmp_path / "cache", tmp_path / "starrydata.duckdb"
    run_ingest(cache_dir=cache_dir, db_path=db_path)
    mtime_before = db_path.stat().st_mtime

    result = run_ingest(cache_dir=cache_dir, db_path=db_path)
    assert result.rebuilt is False
    assert db_path.stat().st_mtime == mtime_before


@respx.mock
def test_force_rebuilds_even_when_snapshot_unchanged(tmp_path: Path) -> None:
    _mock_manifest_and_files("2026-08-15 02:00:02 UTC+0900 (JST)")
    cache_dir, db_path = tmp_path / "cache", tmp_path / "starrydata.duckdb"
    run_ingest(cache_dir=cache_dir, db_path=db_path)

    result = run_ingest(cache_dir=cache_dir, db_path=db_path, force=True)
    assert result.rebuilt is True


@respx.mock
def test_new_snapshot_triggers_rebuild_and_no_stale_tmp_file_left(tmp_path: Path) -> None:
    cache_dir, db_path = tmp_path / "cache", tmp_path / "starrydata.duckdb"
    _mock_manifest_and_files("2026-08-15 02:00:02 UTC+0900 (JST)")
    run_ingest(cache_dir=cache_dir, db_path=db_path)

    respx.reset()
    _mock_manifest_and_files("2026-08-16 02:00:02 UTC+0900 (JST)")
    result = run_ingest(cache_dir=cache_dir, db_path=db_path)

    assert result.rebuilt is True
    assert result.db_snapshot == "2026-08-16 02:00:02 UTC+0900 (JST)"
    assert not db_path.with_suffix(db_path.suffix + ".tmp").exists()

    state = json.loads((cache_dir / "state.json").read_text())
    assert state["db_snapshot"] == "2026-08-16 02:00:02 UTC+0900 (JST)"


def test_parse_db_snapshot_converts_jst_to_utc() -> None:
    dt = _parse_db_snapshot("2026-08-15 02:00:02 UTC+0900 (JST)")
    assert dt is not None
    assert dt.isoformat() == "2026-08-14T17:00:02+00:00"


def test_parse_db_snapshot_unparseable_returns_none() -> None:
    assert _parse_db_snapshot("garbage") is None
