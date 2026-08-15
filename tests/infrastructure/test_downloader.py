from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

import httpx
import pytest
import respx

from starrydata_mcp.infrastructure.ingestion.downloader import (
    MANIFEST_URL,
    RELEASE_BASE_URL,
    ChecksumMismatchError,
    ManifestFile,
    _parse_manifest,
    download_all_data,
    download_and_verify,
    fetch_manifest,
    gunzip,
)

_MANIFEST_PAYLOAD = {
    "generated_at": "2026-08-15T02:00:00+00:00",
    "db_snapshot": "2026-08-15 02:00:02 UTC+0900 (JST)",
    "totals": {"papers": 2, "figures": 3, "samples": 3, "curves": 3},
    "all_data": {
        "papers": {"filename": "all_papers.csv.gz", "rows": 2, "bytes": 10, "sha256": "x"},
        "samples": {"filename": "all_samples.csv.gz", "rows": 3, "bytes": 10, "sha256": "y"},
        "curves": {"filename": "all_curves.csv.gz", "rows": 3, "bytes": 10, "sha256": "z"},
    },
}


@respx.mock
def test_fetch_manifest_parses_payload() -> None:
    respx.get(MANIFEST_URL).mock(return_value=httpx.Response(200, json=_MANIFEST_PAYLOAD))
    with httpx.Client() as client:
        manifest = fetch_manifest(client)
    assert manifest.db_snapshot == "2026-08-15 02:00:02 UTC+0900 (JST)"
    assert manifest.all_data["curves"].sha256 == "z"


@respx.mock
def test_download_and_verify_succeeds_on_matching_checksum(tmp_path: Path) -> None:
    content = b"hello starrydata"
    digest = hashlib.sha256(content).hexdigest()
    manifest_file = ManifestFile(
        filename="all_papers.csv.gz", rows=1, bytes=len(content), sha256=digest
    )
    respx.get(f"{RELEASE_BASE_URL}/all_papers.csv.gz").mock(
        return_value=httpx.Response(200, content=content)
    )
    dest = tmp_path / "all_papers.csv.gz"
    with httpx.Client() as client:
        download_and_verify(client, manifest_file, dest)
    assert dest.read_bytes() == content


@respx.mock
def test_download_and_verify_raises_and_cleans_up_on_mismatch(tmp_path: Path) -> None:
    manifest_file = ManifestFile(filename="all_papers.csv.gz", rows=1, bytes=5, sha256="deadbeef")
    respx.get(f"{RELEASE_BASE_URL}/all_papers.csv.gz").mock(
        return_value=httpx.Response(200, content=b"not matching")
    )
    dest = tmp_path / "all_papers.csv.gz"
    with httpx.Client() as client, pytest.raises(ChecksumMismatchError):
        download_and_verify(client, manifest_file, dest)
    assert not dest.exists()


def test_gunzip_roundtrip(tmp_path: Path) -> None:
    src = tmp_path / "data.csv.gz"
    with gzip.open(src, "wb") as f:
        f.write(b"a,b\n1,2\n")
    dest = tmp_path / "data.csv"
    gunzip(src, dest)
    assert dest.read_bytes() == b"a,b\n1,2\n"


@respx.mock
def test_download_all_data_fetches_all_three_kinds(tmp_path: Path) -> None:
    contents = {
        "papers": b"papers-content",
        "samples": b"samples-content",
        "curves": b"curves-content",
    }
    manifest_payload = dict(_MANIFEST_PAYLOAD)
    manifest_payload["all_data"] = {
        kind: {
            "filename": f"all_{kind}.csv.gz",
            "rows": 1,
            "bytes": len(content),
            "sha256": hashlib.sha256(gzip.compress(content)).hexdigest(),
        }
        for kind, content in contents.items()
    }
    for kind, content in contents.items():
        respx.get(f"{RELEASE_BASE_URL}/all_{kind}.csv.gz").mock(
            return_value=httpx.Response(200, content=gzip.compress(content))
        )

    manifest = _parse_manifest(manifest_payload)
    with httpx.Client() as client:
        csv_paths = download_all_data(client, manifest, tmp_path / "staging")

    for kind, content in contents.items():
        assert csv_paths[kind].read_bytes() == content
