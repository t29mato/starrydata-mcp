from __future__ import annotations

from starrydata_mcp.domain.entities import Paper

from .connection import DuckDBConnectionProvider
from .rowmap import PAPER_COLUMNS, row_to_paper


class DuckDBPaperRepository:
    def __init__(self, provider: DuckDBConnectionProvider) -> None:
        self._provider = provider

    def get_by_sid(self, sid: str) -> Paper | None:
        # `sid` is not always unique upstream (see schema.py's note); ORDER BY
        # keeps the pick deterministic across queries rather than crashing or
        # depending on undefined row order.
        row = self._provider.connection.execute(
            f"SELECT {PAPER_COLUMNS} FROM papers WHERE sid = ? ORDER BY created_at LIMIT 1",
            [sid],
        ).fetchone()
        return row_to_paper(row) if row is not None else None

    def search(
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
    ) -> list[Paper]:
        clauses: list[str] = []
        params: list[object] = []

        if doi:
            clauses.append("doi = ?")
            params.append(doi)
        if author:
            clauses.append(
                "EXISTS (SELECT 1 FROM json_each(authors) je "
                "WHERE lower(je.value->>'family') LIKE '%' || lower(?) || '%')"
            )
            params.append(author)
        if title_keyword:
            clauses.append("lower(title) LIKE '%' || lower(?) || '%'")
            params.append(title_keyword)
        if year_min is not None:
            clauses.append("issued_year >= ?")
            params.append(year_min)
        if year_max is not None:
            clauses.append("issued_year <= ?")
            params.append(year_max)
        if project:
            clauses.append("list_contains(project_names, ?)")
            params.append(project)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT {PAPER_COLUMNS} FROM papers {where} ORDER BY sid LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self._provider.connection.execute(sql, params).fetchall()
        return [row_to_paper(r) for r in rows]
