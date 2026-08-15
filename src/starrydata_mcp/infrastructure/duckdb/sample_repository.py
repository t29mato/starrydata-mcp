from __future__ import annotations

from starrydata_mcp.domain.entities import Sample

from .connection import DuckDBConnectionProvider
from .rowmap import SAMPLE_COLUMNS, row_to_sample


class DuckDBSampleRepository:
    def __init__(self, provider: DuckDBConnectionProvider) -> None:
        self._provider = provider

    def get_by_uid(self, sample_uid: str) -> Sample | None:
        row = self._provider.connection.execute(
            f"SELECT {SAMPLE_COLUMNS} FROM samples WHERE sample_uid = ?", [sample_uid]
        ).fetchone()
        return row_to_sample(row) if row is not None else None

    def list_by_sid(self, sid: str) -> list[Sample]:
        rows = self._provider.connection.execute(
            f"SELECT {SAMPLE_COLUMNS} FROM samples WHERE sid = ? ORDER BY sample_id", [sid]
        ).fetchall()
        return [row_to_sample(r) for r in rows]

    def search(
        self,
        *,
        composition: str | None = None,
        elements: tuple[str, ...] | None = None,
        project: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Sample]:
        clauses: list[str] = []
        params: list[object] = []

        if composition:
            clauses.append("lower(composition_raw) LIKE '%' || lower(?) || '%'")
            params.append(composition)
        if elements:
            for element in elements:
                clauses.append("list_contains(elements, ?)")
                params.append(element)
        if project:
            # Membership mirrors the real dataset's rule (docs/design/
            # architecture.md §1.2): a sample belongs to a project iff one of
            # its curves is tagged with that project.
            clauses.append(
                "sample_uid IN "
                "(SELECT DISTINCT sample_uid FROM curves WHERE list_contains(project_names, ?))"
            )
            params.append(project)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT {SAMPLE_COLUMNS} FROM samples {where} ORDER BY sample_uid LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self._provider.connection.execute(sql, params).fetchall()
        return [row_to_sample(r) for r in rows]
