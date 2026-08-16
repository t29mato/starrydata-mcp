"""Fetches the daily Starrydata snapshot from GitHub Releases.

Design (docs/design/architecture.md §1.4, §2.2): GitHub Releases is the
chosen primary source (not the Google Drive ZIP) because `manifest.json`
gives us a `db_snapshot` string and per-file SHA256 for free, which is what
makes the daily run idempotent and verifiable.
"""

from __future__ import annotations

import gzip
import hashlib
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .progress import ProgressFn, default_progress

MANIFEST_URL = "https://starrydata.github.io/starrydata_datasets/manifest.json"
RELEASE_BASE_URL = "https://github.com/starrydata/starrydata_datasets/releases/latest/download"

_ALL_DATA_FILES = ("papers", "samples", "curves")


class ChecksumMismatchError(RuntimeError):
    def __init__(self, filename: str, expected: str, actual: str) -> None:
        super().__init__(f"{filename}: expected sha256 {expected}, got {actual}")
        self.filename = filename


@dataclass(frozen=True)
class ManifestFile:
    filename: str
    rows: int
    bytes: int
    sha256: str


@dataclass(frozen=True)
class Manifest:
    generated_at: str
    db_snapshot: str
    totals: dict[str, int]
    all_data: dict[str, ManifestFile]
    raw: dict[str, Any]


def _parse_manifest(payload: dict[str, Any]) -> Manifest:
    all_data = {
        kind: ManifestFile(
            filename=info["filename"], rows=info["rows"], bytes=info["bytes"], sha256=info["sha256"]
        )
        for kind, info in payload["all_data"].items()
    }
    return Manifest(
        generated_at=payload["generated_at"],
        db_snapshot=payload["db_snapshot"],
        totals=payload["totals"],
        all_data=all_data,
        raw=payload,
    )


def fetch_manifest(client: httpx.Client) -> Manifest:
    response = client.get(MANIFEST_URL, timeout=30)
    response.raise_for_status()
    return _parse_manifest(response.json())


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_and_verify(
    client: httpx.Client,
    manifest_file: ManifestFile,
    dest_path: Path,
    on_progress: ProgressFn = default_progress,
) -> None:
    """Stream `manifest_file` to `dest_path`, raising `ChecksumMismatchError`
    (and removing the partial download) if the SHA256 doesn't match."""
    url = f"{RELEASE_BASE_URL}/{manifest_file.filename}"
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    size_mb = manifest_file.bytes / 1_000_000
    on_progress(f"Downloading {manifest_file.filename} ({size_mb:.1f} MB)...")
    started = time.monotonic()
    with client.stream("GET", url, timeout=120, follow_redirects=True) as response:
        response.raise_for_status()
        with dest_path.open("wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)
    on_progress(f"  downloaded {manifest_file.filename} in {time.monotonic() - started:.1f}s")

    actual = _sha256_of(dest_path)
    if actual != manifest_file.sha256:
        dest_path.unlink(missing_ok=True)
        raise ChecksumMismatchError(manifest_file.filename, manifest_file.sha256, actual)


def gunzip(src_path: Path, dest_path: Path) -> None:
    with gzip.open(src_path, "rb") as src, dest_path.open("wb") as dest:
        shutil.copyfileobj(src, dest)


def download_all_data(
    client: httpx.Client,
    manifest: Manifest,
    staging_dir: Path,
    on_progress: ProgressFn = default_progress,
) -> dict[str, Path]:
    """Downloads+verifies+decompresses the three `all_*.csv.gz` files.

    Returns `{"papers": Path(.../papers.csv), "samples": ..., "curves": ...}`.
    """
    staging_dir.mkdir(parents=True, exist_ok=True)
    csv_paths: dict[str, Path] = {}
    for kind in _ALL_DATA_FILES:
        manifest_file = manifest.all_data[kind]
        gz_path = staging_dir / manifest_file.filename
        download_and_verify(client, manifest_file, gz_path, on_progress=on_progress)
        csv_path = staging_dir / f"{kind}.csv"
        gunzip(gz_path, csv_path)
        gz_path.unlink()
        csv_paths[kind] = csv_path
    return csv_paths
