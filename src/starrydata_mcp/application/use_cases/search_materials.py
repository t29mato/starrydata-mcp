"""Use case backing the `search_materials` MCP tool."""

from __future__ import annotations

from starrydata_mcp.domain.repositories import CurveRepository, SampleRepository

from ..dto import SampleSummaryDTO
from ..mappers import sample_to_summary_dto


class SearchMaterialsUseCase:
    def __init__(self, sample_repo: SampleRepository, curve_repo: CurveRepository) -> None:
        self._sample_repo = sample_repo
        self._curve_repo = curve_repo

    def execute(
        self,
        *,
        composition: str | None = None,
        elements: tuple[str, ...] | None = None,
        project: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[SampleSummaryDTO]:
        samples = self._sample_repo.search(
            composition=composition,
            elements=elements,
            project=project,
            limit=limit,
            offset=offset,
        )
        return [
            sample_to_summary_dto(s, self._curve_repo.list_by_sample_uid(s.sample_uid))
            for s in samples
        ]
