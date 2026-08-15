"""Integration test: real-shaped fixture CSVs -> build_database -> raw SQL
assertions against the resulting DuckDB file. Repository-level behavior is
covered separately in test_duckdb_repositories.py against the same fixture.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from starrydata_mcp.infrastructure.ingestion.etl import DatasetMetaInput, build_database

FIXTURES = Path(__file__).parent.parent / "fixtures" / "raw"


@pytest.fixture
def built_db(tmp_path: Path) -> Path:
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


def test_row_counts_match_fixtures(built_db: Path) -> None:
    con = duckdb.connect(str(built_db), read_only=True)
    assert con.execute("SELECT count(*) FROM papers").fetchone() == (2,)
    assert con.execute("SELECT count(*) FROM samples").fetchone() == (3,)
    assert con.execute("SELECT count(*) FROM curves").fetchone() == (3,)
    assert con.execute("SELECT count(*) FROM dataset_meta").fetchone() == (1,)
    con.close()


def test_crossref_quoted_title_is_unwrapped(built_db: Path) -> None:
    con = duckdb.connect(str(built_db), read_only=True)
    title = con.execute("SELECT title FROM papers WHERE sid = '6'").fetchone()[0]
    assert title == "Thermoelectric properties of PbTe-based alloys"
    con.close()


def test_issued_date_parts_split_into_columns(built_db: Path) -> None:
    con = duckdb.connect(str(built_db), read_only=True)
    row = con.execute(
        "SELECT issued_year, issued_month, issued_day FROM papers WHERE sid = '6'"
    ).fetchone()
    assert row == (2014, 1, 1)
    con.close()


def test_messy_composition_gets_no_parsed_elements(built_db: Path) -> None:
    con = duckdb.connect(str(built_db), read_only=True)
    elements = con.execute("SELECT elements FROM samples WHERE sample_uid = '6:114'").fetchone()[0]
    assert elements == []
    con.close()


def test_clean_composition_gets_parsed_elements(built_db: Path) -> None:
    con = duckdb.connect(str(built_db), read_only=True)
    elements = con.execute("SELECT elements FROM samples WHERE sample_uid = '6:113'").fetchone()[0]
    assert elements == ["Pb", "Zn", "Te", "I"]
    con.close()


def test_curve_ids_are_surrogate_and_stats_are_materialized(built_db: Path) -> None:
    con = duckdb.connect(str(built_db), read_only=True)
    rows = con.execute(
        "SELECT curve_id, point_count, x_min, x_max, y_min, y_max FROM curves ORDER BY curve_id"
    ).fetchall()
    assert [r[0] for r in rows] == [1, 2, 3]
    zt_row = next(r for r in rows if r[0] == 2)
    assert zt_row[1:] == (2, 300.0, 600.0, 0.2, 1.1)
    con.close()


def test_build_refuses_to_overwrite_existing_file(built_db: Path) -> None:
    with pytest.raises(FileExistsError):
        build_database(
            papers_csv=FIXTURES / "papers.csv",
            samples_csv=FIXTURES / "samples.csv",
            curves_csv=FIXTURES / "curves.csv",
            meta=DatasetMetaInput(
                db_snapshot=None,
                generated_at=datetime(2026, 8, 15, tzinfo=UTC),
                papers=2,
                figures=3,
                samples=3,
                curves=3,
                license="CC BY 4.0",
                citation="",
                source_url="",
            ),
            dest_path=built_db,
        )
