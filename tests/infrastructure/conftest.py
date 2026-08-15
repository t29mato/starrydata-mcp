from __future__ import annotations

from pathlib import Path

import pytest

from starrydata_mcp.infrastructure.duckdb.connection import DuckDBConnectionProvider
from starrydata_mcp.infrastructure.duckdb.curve_repository import DuckDBCurveRepository
from starrydata_mcp.infrastructure.duckdb.dataset_info_repository import (
    DuckDBDatasetInfoRepository,
)
from starrydata_mcp.infrastructure.duckdb.paper_repository import DuckDBPaperRepository
from starrydata_mcp.infrastructure.duckdb.sample_repository import DuckDBSampleRepository

# `db_path` fixture (builds a DuckDB file from tests/fixtures/raw/*.csv) lives
# in tests/conftest.py so tests/interface can reuse it too.


@pytest.fixture
def provider(db_path: Path) -> DuckDBConnectionProvider:
    p = DuckDBConnectionProvider(db_path)
    yield p
    p.close()


@pytest.fixture
def duckdb_paper_repo(provider: DuckDBConnectionProvider) -> DuckDBPaperRepository:
    return DuckDBPaperRepository(provider)


@pytest.fixture
def duckdb_sample_repo(provider: DuckDBConnectionProvider) -> DuckDBSampleRepository:
    return DuckDBSampleRepository(provider)


@pytest.fixture
def duckdb_curve_repo(provider: DuckDBConnectionProvider) -> DuckDBCurveRepository:
    return DuckDBCurveRepository(provider)


@pytest.fixture
def duckdb_dataset_info_repo(
    provider: DuckDBConnectionProvider,
) -> DuckDBDatasetInfoRepository:
    return DuckDBDatasetInfoRepository(provider)
