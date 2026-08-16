"""Orchestrates one daily ingestion run (docs/design/architecture.md §2.2):

    acquire single-instance lock -> clean up any stale leftovers from a
    previous interrupted run -> manifest.json -> (unchanged? skip) ->
    download+verify -> ETL into a `.tmp` DuckDB file -> atomic rename into
    place -> record state.

Never mutates the live `starrydata.duckdb` in place — a crash mid-run
leaves the previous good file untouched, so the MCP server keeps serving
(possibly stale) data rather than breaking.

Bug fix (2026-08-16, reported by the owner): an interrupted run (Ctrl+C
after several silent minutes, because there was no progress output) left a
`starrydata.duckdb.tmp.wal` file behind. The *next* run only ever cleaned up
`starrydata.duckdb.tmp`, not its `.wal` sidecar, so DuckDB's WAL-recovery
logic on the next attempt hit that leftover file and raised a raw
"Could not set lock on ... .wal (Conflicting lock held by PID ...)" error —
confusing, because the actual live database was never touched (the atomic
rename design worked correctly) and no process was really still running.

Fixed with two changes:
  1. An advisory file lock (`cache_dir/ingest.lock`) makes "is another
     ingest actually still running" an explicit, checkable fact instead of
     an inference from a DuckDB-internal error message. If the lock is
     held, we say so clearly and stop — we never guess.
  2. Once the lock is acquired, any `.tmp`/`.tmp.wal`/staging leftovers are
     *guaranteed* to be from a dead process (a live one would be holding
     the lock we just got), so they're safe to remove unconditionally.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import shutil
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from .downloader import Manifest, download_all_data, fetch_manifest
from .etl import DatasetMetaInput, build_database
from .progress import ProgressFn, default_progress

DATASET_LICENSE = "CC BY 4.0"
DATASET_CITATION = (
    "Katsura, Y., Kumagai, M., Mato, T., et al. (2025). Starrydata: from published "
    "plots to shared materials data. Science and Technology of Advanced Materials: "
    "Methods, 5(1), 2506976. https://doi.org/10.1080/27660400.2025.2506976"
)
DATASET_SOURCE_URL = "https://github.com/starrydata/starrydata_datasets"

_JST_SUFFIX = "UTC+0900 (JST)"


@dataclass(frozen=True)
class IngestResult:
    rebuilt: bool
    db_snapshot: str | None
    db_path: Path


class IngestAlreadyRunningError(RuntimeError):
    """Raised when another `starrydata-mcp ingest` genuinely holds the lock."""

    def __init__(self, holder_pid: str) -> None:
        super().__init__(
            f"Another `starrydata-mcp ingest` appears to already be running "
            f"(lock held by PID {holder_pid}). Wait for it to finish and try "
            f"again. If you're sure nothing is actually running (e.g. the "
            f"machine was rebooted), delete the lock file and retry."
        )
        self.holder_pid = holder_pid


def _parse_db_snapshot(raw: str) -> datetime | None:
    """`"2026-08-15 02:00:02 UTC+0900 (JST)"` -> aware UTC datetime.

    Best-effort: an unparseable snapshot string must not abort ingestion —
    `get_dataset_info` just reports it as always-stale (see application
    layer's `GetDatasetInfoUseCase`).
    """
    if not raw.endswith(_JST_SUFFIX):
        return None
    naive_part = raw[: -len(_JST_SUFFIX)].strip()
    try:
        naive = datetime.strptime(naive_part, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    jst_offset_hours = 9
    return (naive - timedelta(hours=jst_offset_hours)).replace(tzinfo=UTC)


def _read_state(state_path: Path) -> str | None:
    if not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text()).get("db_snapshot")
    except (json.JSONDecodeError, OSError):
        return None


def _write_state(state_path: Path, manifest: Manifest) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"db_snapshot": manifest.db_snapshot}))


@contextlib.contextmanager
def _ingest_lock(cache_dir: Path) -> Iterator[None]:
    """POSIX advisory lock so a second concurrent `ingest` fails fast with a
    clear error instead of the two runs corrupting each other's `.tmp` file.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    lock_path = cache_dir / "ingest.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        holder_pid = "unknown"
        with contextlib.suppress(OSError):
            holder_pid = lock_path.read_text().strip() or "unknown"
        os.close(fd)
        raise IngestAlreadyRunningError(holder_pid) from exc

    os.ftruncate(fd, 0)
    os.write(fd, str(os.getpid()).encode())
    os.fsync(fd)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _cleanup_build_files(tmp_db_path: Path, staging_dir: Path, on_progress: ProgressFn) -> None:
    wal_path = tmp_db_path.with_name(tmp_db_path.name + ".wal")
    leftovers = [p for p in (tmp_db_path, wal_path, staging_dir) if p.exists()]
    if leftovers:
        on_progress(
            f"Found {len(leftovers)} leftover file(s) from a previous interrupted "
            "run. The live database was never touched (it's only ever replaced "
            "atomically once a new build finishes) — cleaning up before starting."
        )
    tmp_db_path.unlink(missing_ok=True)
    wal_path.unlink(missing_ok=True)
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)


def run_ingest(
    *,
    cache_dir: Path,
    db_path: Path,
    client: httpx.Client | None = None,
    force: bool = False,
    on_progress: ProgressFn = default_progress,
) -> IngestResult:
    owns_client = client is None
    client = client or httpx.Client()
    started = time.monotonic()
    try:
        with _ingest_lock(cache_dir):
            tmp_db_path = db_path.with_suffix(db_path.suffix + ".tmp")
            staging_dir = cache_dir / "staging"
            _cleanup_build_files(tmp_db_path, staging_dir, on_progress)

            on_progress("Checking for a newer snapshot...")
            manifest = fetch_manifest(client)
            state_path = cache_dir / "state.json"
            previous_snapshot = _read_state(state_path)

            if not force and previous_snapshot == manifest.db_snapshot and db_path.exists():
                on_progress(f"Already up to date (snapshot {manifest.db_snapshot}).")
                return IngestResult(
                    rebuilt=False, db_snapshot=manifest.db_snapshot, db_path=db_path
                )

            on_progress(
                "Downloading and rebuilding — a full run on the complete "
                "dataset typically takes 15-30 minutes (loading ~400k rows "
                "is the slow part, not the ~57 MB download). Progress is "
                "reported throughout, and Ctrl+C is safe at any point; "
                "partial files are cleaned up automatically."
            )
            try:
                csv_paths = download_all_data(
                    client, manifest, staging_dir, on_progress=on_progress
                )

                meta = DatasetMetaInput(
                    db_snapshot=_parse_db_snapshot(manifest.db_snapshot),
                    generated_at=datetime.now(UTC),
                    papers=manifest.totals["papers"],
                    figures=manifest.totals["figures"],
                    samples=manifest.totals["samples"],
                    curves=manifest.totals["curves"],
                    license=DATASET_LICENSE,
                    citation=DATASET_CITATION,
                    source_url=DATASET_SOURCE_URL,
                )
                build_database(
                    papers_csv=csv_paths["papers"],
                    samples_csv=csv_paths["samples"],
                    curves_csv=csv_paths["curves"],
                    meta=meta,
                    dest_path=tmp_db_path,
                    on_progress=on_progress,
                )

                tmp_db_path.replace(db_path)  # atomic on the same filesystem
                shutil.rmtree(staging_dir, ignore_errors=True)
                _write_state(state_path, manifest)
            except BaseException:
                # Covers KeyboardInterrupt too: never leave a half-built .tmp
                # or its .wal sidecar behind for the next run to trip over.
                _cleanup_build_files(tmp_db_path, staging_dir, default_progress)
                raise

            on_progress(f"Done in {time.monotonic() - started:.0f}s.")
            return IngestResult(rebuilt=True, db_snapshot=manifest.db_snapshot, db_path=db_path)
    finally:
        if owns_client:
            client.close()
