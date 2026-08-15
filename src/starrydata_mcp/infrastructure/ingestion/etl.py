"""Builds a fresh DuckDB replica from the raw Starrydata CSVs.

Design (docs/design/architecture.md §2.2): always a full rebuild, never an
incremental merge — simpler and harder to get subtly wrong than diffing
~330MB of upstream CSV daily. The caller is responsible for building into a
`.tmp` path and atomically renaming it into place only after `build_database`
returns successfully (see `pipeline.py`).
"""

from __future__ import annotations

import csv
import itertools
import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import duckdb

from starrydata_mcp.domain.composition import parse_elements
from starrydata_mcp.infrastructure.duckdb.schema import create_schema

from .parsing import (
    parse_authors,
    parse_float_list,
    parse_issued_date,
    parse_sample_info,
    parse_string_list,
    strip_crossref_quoting,
)

_CSV_FIELD_SIZE_LIMIT = 10 * 1024 * 1024  # curve x/y arrays can be long


@dataclass(frozen=True)
class DatasetMetaInput:
    db_snapshot: datetime | None
    generated_at: datetime
    papers: int
    figures: int
    samples: int
    curves: int
    license: str
    citation: str
    source_url: str


def _rows(csv_path: Path) -> Iterator[dict[str, str]]:
    csv.field_size_limit(_CSV_FIELD_SIZE_LIMIT)
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


def _executemany(con: duckdb.DuckDBPyConnection, sql: str, rows: list[tuple[object, ...]]) -> None:
    # DuckDB's executemany rejects an empty parameter list outright; an
    # empty (header-only) source CSV is a legitimate — if unlikely — input.
    if rows:
        con.executemany(sql, rows)


def _load_papers(con: duckdb.DuckDBPyConnection, papers_csv: Path) -> None:
    def gen() -> Iterator[tuple[object, ...]]:
        for row in _rows(papers_csv):
            year, month, day = parse_issued_date(row.get("issued"))
            yield (
                row["SID"],
                row.get("DOI") or None,
                row.get("URL") or None,
                year,
                month,
                day,
                json.dumps(parse_authors(row.get("author"))),
                strip_crossref_quoting(row.get("title")) or None,
                strip_crossref_quoting(row.get("container_title")) or None,
                strip_crossref_quoting(row.get("container_title_short")) or None,
                strip_crossref_quoting(row.get("volume")) or None,
                strip_crossref_quoting(row.get("issue")) or None,
                strip_crossref_quoting(row.get("page")) or None,
                row.get("ISSN") or None,
                row.get("publisher") or None,
                parse_string_list(row.get("project_names")),
                row.get("created_at") or None,
            )

    _executemany(
        con, "INSERT INTO papers VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", list(gen())
    )


def _load_samples(con: duckdb.DuckDBPyConnection, samples_csv: Path) -> None:
    def gen() -> Iterator[tuple[object, ...]]:
        for row in _rows(samples_csv):
            sid = row["SID"]
            sample_id = row["sample_id"]
            composition = row.get("composition") or ""
            yield (
                f"{sid}:{sample_id}",
                sid,
                sample_id,
                row.get("sample_name") or None,
                composition,
                list(parse_elements(composition)),
                row.get("composition_details") or None,
                json.dumps(parse_sample_info(row.get("sample_info"))),
                row.get("created_at") or None,
                row.get("updated_at") or None,
            )

    _executemany(con, "INSERT INTO samples VALUES (?,?,?,?,?,?,?,?,?,?)", list(gen()))


def _load_curves(con: duckdb.DuckDBPyConnection, curves_csv: Path) -> None:
    counter = itertools.count(1)

    def gen() -> Iterator[tuple[object, ...]]:
        for row in _rows(curves_csv):
            xs = parse_float_list(row.get("x"))
            ys = parse_float_list(row.get("y"))
            yield (
                next(counter),
                row["SID"],
                f"{row['SID']}:{row['sample_id']}",
                row.get("DOI") or None,
                row.get("composition") or "",
                row.get("figure_id") or None,
                row.get("figure_name") or None,
                row.get("prop_x") or "",
                row.get("prop_y") or "",
                row.get("unit_x") or None,
                row.get("unit_y") or None,
                xs,
                ys,
                parse_string_list(row.get("project_names")),
                row.get("comments") or None,
                len(xs),
                min(xs) if xs else None,
                max(xs) if xs else None,
                min(ys) if ys else None,
                max(ys) if ys else None,
            )

    _executemany(
        con,
        "INSERT INTO curves VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        list(gen()),
    )


def _load_meta(con: duckdb.DuckDBPyConnection, meta: DatasetMetaInput) -> None:
    con.execute(
        "INSERT INTO dataset_meta VALUES (?,?,?,?,?,?,?,?,?)",
        [
            meta.db_snapshot,
            meta.generated_at,
            meta.papers,
            meta.figures,
            meta.samples,
            meta.curves,
            meta.license,
            meta.citation,
            meta.source_url,
        ],
    )


def build_database(
    *,
    papers_csv: Path,
    samples_csv: Path,
    curves_csv: Path,
    meta: DatasetMetaInput,
    dest_path: Path,
) -> None:
    """Build a brand-new DuckDB file at `dest_path` from the three raw CSVs.

    `dest_path` must not already exist (the caller builds into a `.tmp` path
    and renames — see `pipeline.py` — so a stale half-built file is never
    mistaken for a good one).
    """
    if dest_path.exists():
        raise FileExistsError(
            f"{dest_path} already exists; build into a fresh path and rename it into place"
        )
    con = duckdb.connect(str(dest_path))
    try:
        create_schema(con)
        _load_papers(con, papers_csv)
        _load_samples(con, samples_csv)
        _load_curves(con, curves_csv)
        _load_meta(con, meta)
    finally:
        con.close()
