"""Orchestrates one daily ingestion run (docs/design/architecture.md §2.2):

    manifest.json -> (unchanged? skip) -> download+verify -> ETL into a
    `.tmp` DuckDB file -> atomic rename into place -> record state.

Never mutates the live `starrydata.duckdb` in place — a crash mid-run
leaves the previous good file untouched, so the MCP server keeps serving
(possibly stale) data rather than breaking.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from .downloader import Manifest, download_all_data, fetch_manifest
from .etl import DatasetMetaInput, build_database

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


def run_ingest(
    *,
    cache_dir: Path,
    db_path: Path,
    client: httpx.Client | None = None,
    force: bool = False,
) -> IngestResult:
    owns_client = client is None
    client = client or httpx.Client()
    try:
        manifest = fetch_manifest(client)
        state_path = cache_dir / "state.json"
        previous_snapshot = _read_state(state_path)

        if not force and previous_snapshot == manifest.db_snapshot and db_path.exists():
            return IngestResult(
                rebuilt=False, db_snapshot=manifest.db_snapshot, db_path=db_path
            )

        staging_dir = cache_dir / "staging"
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        csv_paths = download_all_data(client, manifest, staging_dir)

        tmp_db_path = db_path.with_suffix(db_path.suffix + ".tmp")
        tmp_db_path.unlink(missing_ok=True)

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
        )

        tmp_db_path.replace(db_path)  # atomic on the same filesystem
        shutil.rmtree(staging_dir, ignore_errors=True)
        _write_state(state_path, manifest)

        return IngestResult(rebuilt=True, db_snapshot=manifest.db_snapshot, db_path=db_path)
    finally:
        if owns_client:
            client.close()
