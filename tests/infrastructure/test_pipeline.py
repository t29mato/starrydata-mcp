from __future__ import annotations

import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path

import duckdb
import httpx
import pytest
import respx

from starrydata_mcp.infrastructure.ingestion import pipeline as pipeline_module
from starrydata_mcp.infrastructure.ingestion.downloader import MANIFEST_URL, RELEASE_BASE_URL
from starrydata_mcp.infrastructure.ingestion.pipeline import (
    IngestAlreadyRunningError,
    _parse_db_snapshot,
    run_ingest,
)

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


# --- 2026-08-16 bug fix regression tests -----------------------------------
# Owner-reported bug: a silent ingest looked hung, got Ctrl+C'd, and the
# retry failed with a raw DuckDB "Conflicting lock held by PID ..." error on
# a leftover .wal file. See pipeline.py's module docstring for the full
# root-cause writeup.


@respx.mock
def test_progress_callback_reports_time_estimate_and_stages(tmp_path: Path) -> None:
    _mock_manifest_and_files("2026-08-15 02:00:02 UTC+0900 (JST)")
    messages: list[str] = []
    run_ingest(
        cache_dir=tmp_path / "cache",
        db_path=tmp_path / "starrydata.duckdb",
        on_progress=messages.append,
    )
    joined = "\n".join(messages)
    assert "15-30 minutes" in joined
    assert "Downloading all_papers.csv.gz" in joined
    assert "Loading curves..." in joined
    assert "Done in" in joined


def test_concurrent_ingest_raises_clear_error_instead_of_corrupting(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    lock_path = cache_dir / "ingest.lock"
    # Simulate another live process holding the lock (a second `os.open` +
    # `flock` from *this* process still conflicts, per POSIX flock semantics
    # being per-open-file-description, not per-process).
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    os.write(fd, b"424242")
    os.fsync(fd)
    try:
        with pytest.raises(IngestAlreadyRunningError) as excinfo:
            run_ingest(cache_dir=cache_dir, db_path=tmp_path / "starrydata.duckdb")
        assert "424242" in str(excinfo.value)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@respx.mock
def test_stale_tmp_and_wal_from_a_dead_run_are_cleaned_up_automatically(
    tmp_path: Path,
) -> None:
    cache_dir, db_path = tmp_path / "cache", tmp_path / "starrydata.duckdb"
    cache_dir.mkdir()
    tmp_db_path = db_path.with_suffix(db_path.suffix + ".tmp")
    wal_path = tmp_db_path.with_name(tmp_db_path.name + ".wal")
    tmp_db_path.write_bytes(b"partial-build-from-a-crashed-run")
    wal_path.write_bytes(b"leftover-wal")
    (cache_dir / "staging").mkdir()
    (cache_dir / "staging" / "leftover.csv.gz").write_bytes(b"partial-download")

    _mock_manifest_and_files("2026-08-15 02:00:02 UTC+0900 (JST)")
    messages: list[str] = []
    result = run_ingest(cache_dir=cache_dir, db_path=db_path, on_progress=messages.append)

    assert result.rebuilt is True
    assert not tmp_db_path.exists()
    assert not wal_path.exists()
    assert any("leftover" in m.lower() for m in messages)


@respx.mock
def test_interrupted_build_cleans_up_tmp_and_wal_then_reraises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir, db_path = tmp_path / "cache", tmp_path / "starrydata.duckdb"
    tmp_db_path = db_path.with_suffix(db_path.suffix + ".tmp")
    wal_path = tmp_db_path.with_name(tmp_db_path.name + ".wal")

    real_build_database = pipeline_module.build_database

    def fake_build_database(*, dest_path: Path, **_kwargs: object) -> None:
        # Simulate DuckDB having created its files before Ctrl+C lands.
        dest_path.write_bytes(b"half-built")
        wal_path.write_bytes(b"in-progress-wal")
        raise KeyboardInterrupt

    monkeypatch.setattr(pipeline_module, "build_database", fake_build_database)
    _mock_manifest_and_files("2026-08-15 02:00:02 UTC+0900 (JST)")

    with pytest.raises(KeyboardInterrupt):
        run_ingest(cache_dir=cache_dir, db_path=db_path)

    assert not tmp_db_path.exists()
    assert not wal_path.exists()
    assert not db_path.exists()  # the live db is only ever touched by the atomic rename

    # A subsequent run (with the real build_database restored) must succeed
    # cleanly — no leftover lock from the interrupted run (the `finally` in
    # `_ingest_lock` must have released it).
    monkeypatch.setattr(pipeline_module, "build_database", real_build_database)
    respx.reset()
    _mock_manifest_and_files("2026-08-15 02:00:02 UTC+0900 (JST)")
    result = run_ingest(cache_dir=cache_dir, db_path=db_path)
    assert result.rebuilt is True
