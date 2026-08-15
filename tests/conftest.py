"""Shared across tests/infrastructure and tests/interface: a DuckDB file
built from the real-shaped fixture CSVs in tests/fixtures/raw/*.csv.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from starrydata_mcp.infrastructure.ingestion.etl import DatasetMetaInput, build_database

FIXTURES = Path(__file__).parent / "fixtures" / "raw"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    dest = tmp_path / "starrydata.duckdb"
    build_database(
        papers_csv=FIXTURES / "papers.csv",
        samples_csv=FIXTURES / "samples.csv",
        curves_csv=FIXTURES / "curves.csv",
        meta=DatasetMetaInput(
            db_snapshot=datetime(2026, 8, 15, 2, 0, 0, tzinfo=UTC),
            generated_at=datetime(2026, 8, 15, 2, 5, 0, tzinfo=UTC),
            papers=2,
            figures=3,
            samples=3,
            curves=3,
            license="CC BY 4.0",
            citation="Katsura et al. (2025).",
            source_url="https://github.com/starrydata/starrydata_datasets",
        ),
        dest_path=dest,
    )
    return dest
