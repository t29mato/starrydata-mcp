from __future__ import annotations

from datetime import UTC, datetime

from starrydata_mcp.domain.entities import DatasetInfo, DatasetTotals

from .connection import DuckDBConnectionProvider


def _as_utc(value: datetime | None) -> datetime | None:
    """DuckDB's TIMESTAMP columns round-trip as naive datetimes (TIMESTAMPTZ
    would need the optional `pytz` dependency just for this). ETL always
    normalizes to UTC before insert (see pipeline.py's `_parse_db_snapshot`
    and `datetime.now(UTC)`), so it's safe to reattach UTC here on read.
    """
    if value is None:
        return None
    return value.replace(tzinfo=UTC)


class DuckDBDatasetInfoRepository:
    def __init__(self, provider: DuckDBConnectionProvider) -> None:
        self._provider = provider

    def get_info(self) -> DatasetInfo:
        row = self._provider.connection.execute(
            "SELECT db_snapshot, generated_at, papers, figures, samples, curves, "
            "license, citation, source_url FROM dataset_meta LIMIT 1"
        ).fetchone()
        if row is None:
            raise RuntimeError(
                "dataset_meta is empty — the local DuckDB file was not built by "
                "`starrydata-mcp ingest`"
            )
        (
            db_snapshot,
            generated_at,
            papers,
            figures,
            samples,
            curves,
            license_,
            citation,
            source_url,
        ) = row
        return DatasetInfo(
            db_snapshot=_as_utc(db_snapshot),
            generated_at=_as_utc(generated_at),
            totals=DatasetTotals(papers=papers, figures=figures, samples=samples, curves=curves),
            license=license_,
            citation=citation,
            source_url=source_url,
        )
