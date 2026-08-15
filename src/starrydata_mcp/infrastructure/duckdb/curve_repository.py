from __future__ import annotations

from starrydata_mcp.domain.entities import Curve, CurveSummary, PropertyUsage

from .connection import DuckDBConnectionProvider
from .rowmap import (
    CURVE_FULL_COLUMNS,
    CURVE_SUMMARY_COLUMNS,
    row_to_curve,
    row_to_curve_summary,
)


class DuckDBCurveRepository:
    def __init__(self, provider: DuckDBConnectionProvider) -> None:
        self._provider = provider

    def get_by_ids(self, curve_ids: tuple[int, ...]) -> list[Curve]:
        if not curve_ids:
            return []
        placeholders = ", ".join("?" for _ in curve_ids)
        rows = self._provider.connection.execute(
            f"SELECT {CURVE_FULL_COLUMNS} FROM curves WHERE curve_id IN ({placeholders})",
            list(curve_ids),
        ).fetchall()
        by_id = {r[0]: row_to_curve(r) for r in rows}
        return [by_id[i] for i in curve_ids if i in by_id]

    def list_by_sample_uid(self, sample_uid: str) -> list[CurveSummary]:
        rows = self._provider.connection.execute(
            f"SELECT {CURVE_SUMMARY_COLUMNS} FROM curves WHERE sample_uid = ? ORDER BY curve_id",
            [sample_uid],
        ).fetchall()
        return [row_to_curve_summary(r) for r in rows]

    def list_by_sid(self, sid: str) -> list[CurveSummary]:
        rows = self._provider.connection.execute(
            f"SELECT {CURVE_SUMMARY_COLUMNS} FROM curves WHERE sid = ? ORDER BY curve_id",
            [sid],
        ).fetchall()
        return [row_to_curve_summary(r) for r in rows]

    def search(
        self,
        *,
        prop_x: str | None = None,
        prop_y: str | None = None,
        composition: str | None = None,
        elements: tuple[str, ...] | None = None,
        x_min: float | None = None,
        x_max: float | None = None,
        project: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[CurveSummary]:
        clauses: list[str] = []
        params: list[object] = []

        if prop_x:
            clauses.append("prop_x = ?")
            params.append(prop_x)
        if prop_y:
            clauses.append("prop_y = ?")
            params.append(prop_y)
        if composition:
            clauses.append("lower(composition_raw) LIKE '%' || lower(?) || '%'")
            params.append(composition)
        if elements:
            clauses.append(
                "sample_uid IN "
                "(SELECT sample_uid FROM samples WHERE "
                + " AND ".join("list_contains(elements, ?)" for _ in elements)
                + ")"
            )
            params.extend(elements)
        if x_min is not None:
            # curve overlaps [x_min, x_max] iff it has a point >= x_min
            clauses.append("x_max >= ?")
            params.append(x_min)
        if x_max is not None:
            clauses.append("x_min <= ?")
            params.append(x_max)
        if project:
            clauses.append("list_contains(project_names, ?)")
            params.append(project)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            f"SELECT {CURVE_SUMMARY_COLUMNS} FROM curves {where} ORDER BY curve_id LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        rows = self._provider.connection.execute(sql, params).fetchall()
        return [row_to_curve_summary(r) for r in rows]

    def list_properties(
        self, *, project: str | None = None, top_n: int = 50
    ) -> list[PropertyUsage]:
        where = "WHERE list_contains(project_names, ?)" if project else ""
        params: list[object] = [project] if project else []
        sql = f"""
            SELECT prop_x, prop_y, any_value(unit_x), any_value(unit_y), count(*) AS n
            FROM curves
            {where}
            GROUP BY prop_x, prop_y
            ORDER BY n DESC
            LIMIT ?
        """
        params.append(top_n)
        rows = self._provider.connection.execute(sql, params).fetchall()
        return [
            PropertyUsage(prop_x=r[0], prop_y=r[1], unit_x=r[2], unit_y=r[3], curve_count=r[4])
            for r in rows
        ]
