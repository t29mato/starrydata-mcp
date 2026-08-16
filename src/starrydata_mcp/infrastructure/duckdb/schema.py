"""DuckDB schema for the local Starrydata replica (docs/design/architecture.md §2.3)."""

from __future__ import annotations

import duckdb

TABLES_DDL = """
-- NOTE: `sid` is NOT a reliable primary key in the real dataset — a small
-- number of `sid` values are shared by two entirely unrelated papers
-- (different DOI/title), confirmed by ingesting the live GitHub Releases
-- data (e.g. sid=18526 has two rows: DOI 10.1088/0022-3727/45/21/215308 and
-- 10.1103/physrevb.69.045107). Likely an upstream data-entry artifact; not
-- something this project can correct. `get_by_sid` picks one deterministic
-- row (see paper_repository.py) rather than crashing or guessing which is
-- "right" — flagged for HQ in docs/design/architecture.md §5.
CREATE TABLE papers (
    sid VARCHAR,
    doi VARCHAR,
    url VARCHAR,
    issued_year INTEGER,
    issued_month INTEGER,
    issued_day INTEGER,
    authors JSON,  -- list of {"given": ..., "family": ...}; see infra row mapping
    title VARCHAR,
    container_title VARCHAR,
    container_title_short VARCHAR,
    volume VARCHAR,
    issue VARCHAR,
    page VARCHAR,
    issn VARCHAR,
    publisher VARCHAR,
    project_names VARCHAR[],
    created_at VARCHAR
);

-- No PRIMARY KEY/index here on purpose — see create_indexes() below.
CREATE TABLE samples (
    sample_uid VARCHAR,
    sid VARCHAR,
    sample_id VARCHAR,
    sample_name VARCHAR,
    composition_raw VARCHAR,
    elements VARCHAR[],
    composition_details VARCHAR,
    sample_info_raw JSON,
    created_at VARCHAR,
    updated_at VARCHAR
);

CREATE TABLE curves (
    curve_id BIGINT,
    sid VARCHAR,
    sample_uid VARCHAR,
    doi VARCHAR,
    composition_raw VARCHAR,
    figure_id VARCHAR,
    figure_name VARCHAR,
    prop_x VARCHAR,
    prop_y VARCHAR,
    unit_x VARCHAR,
    unit_y VARCHAR,
    x DOUBLE[],
    y DOUBLE[],
    project_names VARCHAR[],
    comments VARCHAR,
    point_count INTEGER,
    x_min DOUBLE,
    x_max DOUBLE,
    y_min DOUBLE,
    y_max DOUBLE
);

CREATE TABLE dataset_meta (
    db_snapshot TIMESTAMP,
    generated_at TIMESTAMP,
    papers INTEGER,
    figures INTEGER,
    samples INTEGER,
    curves INTEGER,
    license VARCHAR,
    citation VARCHAR,
    source_url VARCHAR
);
"""

# Bug fix (2026-08-16): indexes must be built *after* bulk loading, not
# before. Confirmed empirically: with indexes (incl. the PRIMARY KEYs that
# were here) in place before loading, DuckDB's cost per `executemany` chunk
# grew catastrophically — ~46s per 5,000-row chunk into `curves` (would be
# ~30+ minutes for the real ~234k-row table, vs. a couple of minutes when
# building the same indexes once, after loading, on a real full ingest).
# Incremental index/constraint maintenance during many small inserts is far
# more expensive than one bulk index build at the end — this is standard DB
# practice, but easy to get backwards when adding indexes to a schema you
# also want progress-chunked inserts into. `sample_uid`/`curve_id`
# uniqueness is guaranteed by construction in etl.py (surrogate curve_id via
# itertools.count; sample_uid is `f"{sid}:{sample_id}"` from the source
# data's own composite key) rather than enforced by the database, so these
# are plain indexes for lookup speed, not PRIMARY KEY/UNIQUE constraints.
INDEXES_DDL = """
CREATE INDEX idx_papers_sid ON papers (sid);
CREATE INDEX idx_samples_uid ON samples (sample_uid);
CREATE INDEX idx_samples_sid ON samples (sid);
CREATE INDEX idx_curves_id ON curves (curve_id);
CREATE INDEX idx_curves_sid ON curves (sid);
CREATE INDEX idx_curves_sample_uid ON curves (sample_uid);
CREATE INDEX idx_curves_prop ON curves (prop_x, prop_y);
"""


def create_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(TABLES_DDL)


def create_indexes(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(INDEXES_DDL)
