"""Regression test for a real data-quality issue found by ingesting the live
dataset (not covered by the curated fixtures): `SID` is not always unique in
`all_papers.csv` — some `sid` values are shared by two unrelated papers
(different DOI/title). See schema.py's note and docs/design/architecture.md
§5 for the real example (sid=18526).

ETL must not crash on this, and `get_by_sid` must return one deterministic
row rather than erroring or depending on undefined SQL row order.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

import pytest

from starrydata_mcp.infrastructure.duckdb.connection import DuckDBConnectionProvider
from starrydata_mcp.infrastructure.duckdb.paper_repository import DuckDBPaperRepository
from starrydata_mcp.infrastructure.ingestion.etl import DatasetMetaInput, build_database

_PAPERS_HEADER = [
    "SID", "DOI", "URL", "issued", "author", "title", "container_title",
    "container_title_short", "volume", "issue", "page", "ISSN", "publisher",
    "project_names", "created_at",
]


def _write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def db_with_duplicate_sid(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    _write_csv(
        raw / "papers.csv",
        _PAPERS_HEADER,
        [
            {
                "SID": "18526", "DOI": "10.1088/0022-3727/45/21/215308",
                "URL": "", "issued": "", "author": "[]",
                "title": '"Evaluation of the thermoelectric potential"',
                "container_title": "", "container_title_short": "", "volume": "",
                "issue": "", "page": "", "ISSN": "", "publisher": "",
                "project_names": "[]", "created_at": "2018-01-25T17:21:24",
            },
            {
                "SID": "18526", "DOI": "10.1103/physrevb.69.045107",
                "URL": "", "issued": "", "author": "[]",
                "title": '"Thermal conductivity of thermoelectric clathrates"',
                "container_title": "", "container_title_short": "", "volume": "",
                "issue": "", "page": "", "ISSN": "", "publisher": "",
                "project_names": "[]", "created_at": "2018-01-25T14:18:50",
            },
        ],
    )
    (raw / "samples.csv").write_text(
        "sample_name,sample_id,composition,composition_details,SID,DOI,created_at,"
        "updated_at,sample_info\n",
        encoding="utf-8-sig",
    )
    (raw / "curves.csv").write_text(
        "SID,DOI,composition,sample_id,figure_id,figure_name,prop_x,prop_y,unit_x,"
        "unit_y,x,y,created_at,updated_at,project_names,comments\n",
        encoding="utf-8-sig",
    )

    dest = tmp_path / "starrydata.duckdb"
    build_database(
        papers_csv=raw / "papers.csv",
        samples_csv=raw / "samples.csv",
        curves_csv=raw / "curves.csv",
        meta=DatasetMetaInput(
            db_snapshot=datetime(2026, 8, 15, tzinfo=UTC),
            generated_at=datetime(2026, 8, 15, tzinfo=UTC),
            papers=2, figures=0, samples=0, curves=0,
            license="CC BY 4.0", citation="", source_url="",
        ),
        dest_path=dest,
    )
    return dest


def test_etl_does_not_crash_on_duplicate_sid(db_with_duplicate_sid: Path) -> None:
    assert db_with_duplicate_sid.exists()


def test_get_by_sid_deterministically_returns_one_row(db_with_duplicate_sid: Path) -> None:
    provider = DuckDBConnectionProvider(db_with_duplicate_sid)
    repo = DuckDBPaperRepository(provider)
    first_call = repo.get_by_sid("18526")
    second_call = repo.get_by_sid("18526")
    assert first_call is not None
    assert first_call.doi == second_call.doi  # deterministic, not row-order-dependent
    provider.close()
