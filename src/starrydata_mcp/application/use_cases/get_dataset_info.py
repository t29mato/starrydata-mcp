"""Use case backing the `get_dataset_info` MCP tool."""

from __future__ import annotations

from datetime import timedelta

from starrydata_mcp.domain.repositories import Clock, DatasetInfoRepository

from ..dto import DatasetInfoDTO

_DEFAULT_STALE_AFTER = timedelta(hours=24)


class GetDatasetInfoUseCase:
    def __init__(
        self,
        dataset_info_repo: DatasetInfoRepository,
        clock: Clock,
        stale_after: timedelta = _DEFAULT_STALE_AFTER,
    ) -> None:
        self._repo = dataset_info_repo
        self._clock = clock
        self._stale_after = stale_after

    def execute(self) -> DatasetInfoDTO:
        info = self._repo.get_info()
        is_stale = info.db_snapshot is None or (
            self._clock.now() - info.db_snapshot > self._stale_after
        )
        return DatasetInfoDTO(
            db_snapshot=info.db_snapshot,
            generated_at=info.generated_at,
            papers=info.totals.papers,
            figures=info.totals.figures,
            samples=info.totals.samples,
            curves=info.totals.curves,
            license=info.license,
            citation=info.citation,
            source_url=info.source_url,
            is_stale=is_stale,
        )
