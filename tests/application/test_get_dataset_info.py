from dataclasses import replace
from datetime import UTC, datetime, timedelta

from starrydata_mcp.application.use_cases.get_dataset_info import GetDatasetInfoUseCase
from starrydata_mcp.domain.entities import DatasetInfo, DatasetTotals

from .conftest import FakeClock, FakeDatasetInfoRepository


def _info(db_snapshot: datetime) -> DatasetInfo:
    return DatasetInfo(
        db_snapshot=db_snapshot,
        generated_at=db_snapshot,
        totals=DatasetTotals(papers=1, figures=1, samples=1, curves=1),
        license="CC BY 4.0",
        citation="Katsura et al. (2025).",
        source_url="https://github.com/starrydata/starrydata_datasets",
    )


def test_fresh_snapshot_is_not_stale() -> None:
    now = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    repo = FakeDatasetInfoRepository(_info(now - timedelta(hours=1)))
    use_case = GetDatasetInfoUseCase(repo, FakeClock(now))
    result = use_case.execute()
    assert result.is_stale is False
    assert result.license == "CC BY 4.0"
    assert result.papers == 1


def test_snapshot_older_than_24h_is_stale() -> None:
    now = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    repo = FakeDatasetInfoRepository(_info(now - timedelta(hours=25)))
    use_case = GetDatasetInfoUseCase(repo, FakeClock(now))
    result = use_case.execute()
    assert result.is_stale is True


def test_missing_snapshot_is_always_stale() -> None:
    """No snapshot yet (ingestion never ran) must read as stale, not crash."""
    now = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    repo = FakeDatasetInfoRepository(replace(_info(now), db_snapshot=None))
    use_case = GetDatasetInfoUseCase(repo, FakeClock(now))
    result = use_case.execute()
    assert result.is_stale is True
