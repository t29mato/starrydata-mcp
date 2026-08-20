"""Repository-level integration tests against a DuckDB file built from the
real-shaped fixture CSVs (tests/fixtures/raw/*.csv). These exercise the
actual SQL, not fakes — see docs/design/architecture.md §5 risk notes for
why the composition/element-based filters need real coverage.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from starrydata_mcp.infrastructure.duckdb.connection import DuckDBConnectionProvider
from starrydata_mcp.infrastructure.duckdb.dataset_info_repository import (
    DuckDBDatasetInfoRepository,
)
from starrydata_mcp.infrastructure.duckdb.schema import create_tables
from starrydata_mcp.infrastructure.ingestion.etl import DatasetMetaInput, build_database

FIXTURES = Path(__file__).parent.parent / "fixtures" / "raw"


def test_paper_get_by_sid(duckdb_paper_repo) -> None:
    paper = duckdb_paper_repo.get_by_sid("6")
    assert paper is not None
    assert paper.doi == "10.1021/am405410e"
    assert paper.issued_year == 2014
    assert paper.authors[0].family == "Xiao"
    assert paper.project_names == ("ThermoelectricMaterials",)


def test_paper_get_by_sid_unknown_returns_none(duckdb_paper_repo) -> None:
    assert duckdb_paper_repo.get_by_sid("does-not-exist") is None


def test_paper_search_by_doi(duckdb_paper_repo) -> None:
    [paper] = duckdb_paper_repo.search(doi="10.1000/battery.example")
    assert paper.sid == "42"


def test_paper_search_by_author_substring(duckdb_paper_repo) -> None:
    [paper] = duckdb_paper_repo.search(author="xiao")  # case-insensitive
    assert paper.sid == "6"


def test_paper_search_by_title_keyword(duckdb_paper_repo) -> None:
    [paper] = duckdb_paper_repo.search(title_keyword="cathode")
    assert paper.sid == "42"


def test_paper_search_by_year_range(duckdb_paper_repo) -> None:
    results = duckdb_paper_repo.search(year_min=2018)
    assert [p.sid for p in results] == ["42"]


def test_paper_search_by_year_max(duckdb_paper_repo) -> None:
    results = duckdb_paper_repo.search(year_max=2018)
    assert [p.sid for p in results] == ["6"]


def test_paper_search_by_project(duckdb_paper_repo) -> None:
    results = duckdb_paper_repo.search(project="ThermoelectricMaterials")
    assert [p.sid for p in results] == ["6"]


def test_sample_get_by_uid(duckdb_sample_repo) -> None:
    sample = duckdb_sample_repo.get_by_uid("6:113")
    assert sample is not None
    assert sample.elements == ("Pb", "Zn", "Te", "I")
    assert sample.sample_info_raw["FabricationProcess"]["category"] == "SolidState"


def test_sample_list_by_sid(duckdb_sample_repo) -> None:
    samples = duckdb_sample_repo.list_by_sid("6")
    assert {s.sample_uid for s in samples} == {"6:113", "6:114"}


def test_sample_search_by_composition_substring(duckdb_sample_repo) -> None:
    results = duckdb_sample_repo.search(composition="Pb1.00025")
    assert [s.sample_uid for s in results] == ["6:113"]


def test_sample_search_by_elements_and_semantics(duckdb_sample_repo) -> None:
    results = duckdb_sample_repo.search(elements=("Pb", "Te"))
    assert [s.sample_uid for s in results] == ["6:113"]
    assert duckdb_sample_repo.search(elements=("Pb", "Au")) == []


def test_sample_search_by_project_via_curve_membership(duckdb_sample_repo) -> None:
    results = duckdb_sample_repo.search(project="BatteryMaterials")
    assert [s.sample_uid for s in results] == ["42:1"]


def test_curve_get_by_ids_preserves_request_order(duckdb_curve_repo) -> None:
    curves = duckdb_curve_repo.get_by_ids((2, 1))
    assert [c.curve_id for c in curves] == [2, 1]
    assert curves[1].x == (300.0, 350.0, 400.0)


def test_curve_get_by_ids_skips_unknown(duckdb_curve_repo) -> None:
    curves = duckdb_curve_repo.get_by_ids((1, 999))
    assert [c.curve_id for c in curves] == [1]


def test_curve_get_by_ids_empty_request_short_circuits(duckdb_curve_repo) -> None:
    # No SQL round-trip for an empty request — just an early return.
    assert duckdb_curve_repo.get_by_ids(()) == []


def test_curve_list_by_sample_uid(duckdb_curve_repo) -> None:
    summaries = duckdb_curve_repo.list_by_sample_uid("6:113")
    assert {s.curve_id for s in summaries} == {1, 2}


def test_curve_search_by_property_pair(duckdb_curve_repo) -> None:
    [summary] = duckdb_curve_repo.search(prop_x="Temperature", prop_y="ZT")
    assert summary.curve_id == 2
    assert summary.x_min == 300.0
    assert summary.x_max == 600.0


def test_curve_search_by_x_range_overlap(duckdb_curve_repo) -> None:
    results = duckdb_curve_repo.search(prop_x="Temperature", x_min=500, x_max=700)
    assert [r.curve_id for r in results] == [2]


def test_curve_search_by_composition_substring(duckdb_curve_repo) -> None:
    results = duckdb_curve_repo.search(composition="Pb1.00025")
    assert [r.curve_id for r in results] == [1, 2]


def test_curve_search_by_elements(duckdb_curve_repo) -> None:
    results = duckdb_curve_repo.search(elements=("Li",))
    assert [r.curve_id for r in results] == [3]


def test_curve_search_by_project(duckdb_curve_repo) -> None:
    results = duckdb_curve_repo.search(project="BatteryMaterials")
    assert [r.curve_id for r in results] == [3]


def test_curve_list_properties_ranked_by_count(duckdb_curve_repo) -> None:
    usages = duckdb_curve_repo.list_properties()
    assert len(usages) == 3
    assert all(u.curve_count == 1 for u in usages)


def test_curve_list_properties_project_filter(duckdb_curve_repo) -> None:
    usages = duckdb_curve_repo.list_properties(project="BatteryMaterials")
    assert [(u.prop_x, u.prop_y) for u in usages] == [("Discharge capacity", "Voltage")]


def test_dataset_info_reads_meta_row(duckdb_dataset_info_repo) -> None:
    info = duckdb_dataset_info_repo.get_info()
    assert info.license == "CC BY 4.0"
    assert info.totals.papers == 2
    assert info.totals.curves == 3


def test_dataset_info_null_db_snapshot_stays_none(tmp_path: Path) -> None:
    # Realistic: pipeline.py's _parse_db_snapshot() returns None when the
    # upstream manifest's snapshot string doesn't parse, and that None is
    # written straight through to the TIMESTAMP column.
    dest = tmp_path / "starrydata.duckdb"
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
        dest_path=dest,
    )
    provider = DuckDBConnectionProvider(dest)
    repo = DuckDBDatasetInfoRepository(provider)
    info = repo.get_info()
    assert info.db_snapshot is None
    assert info.generated_at is not None
    provider.close()


def test_dataset_info_raises_on_empty_meta_table(tmp_path: Path) -> None:
    # A DuckDB file with the right tables but no dataset_meta row (e.g. one
    # not built by `starrydata-mcp ingest`) must fail loudly, not silently.
    dest = tmp_path / "empty.duckdb"
    con = duckdb.connect(str(dest))
    create_tables(con)
    con.close()

    provider = DuckDBConnectionProvider(dest)
    repo = DuckDBDatasetInfoRepository(provider)
    try:
        with pytest.raises(RuntimeError, match="dataset_meta is empty"):
            repo.get_info()
    finally:
        provider.close()
