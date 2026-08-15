"""Use case backing the `search_papers` MCP tool."""

from __future__ import annotations

from starrydata_mcp.domain.repositories import PaperRepository

from ..dto import PaperSummaryDTO
from ..mappers import paper_to_summary_dto


class SearchPapersUseCase:
    def __init__(self, paper_repo: PaperRepository) -> None:
        self._paper_repo = paper_repo

    def execute(
        self,
        *,
        doi: str | None = None,
        author: str | None = None,
        title_keyword: str | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        project: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PaperSummaryDTO]:
        papers = self._paper_repo.search(
            doi=doi,
            author=author,
            title_keyword=title_keyword,
            year_min=year_min,
            year_max=year_max,
            project=project,
            limit=limit,
            offset=offset,
        )
        return [paper_to_summary_dto(p) for p in papers]
