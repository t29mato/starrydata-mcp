# Release Notes (Draft)

## v0.1.0 (unreleased)

### Initial MVP: Complete MCP server for Starrydata materials-science dataset

**Architecture & Design**
- Clean-architecture 3-layer implementation (domain/application/infrastructure) with zero production dependencies in the domain layer
- Dependency enforcement via `import-linter` CI contract
- Full test-driven development: 127 tests, 98% code coverage
- Type-safe throughout with `mypy --strict` on domain and application layers

**Features**
- **8 MCP tools** exposing Starrydata's public dataset:
  - `search_materials` — find samples by composition/elements/domain
  - `get_sample_detail` — fetch metadata and curve index for one sample
  - `list_properties` — browse measured-property vocabulary
  - `search_curves` — search by property pair, composition, x-axis range, domain
  - `get_curve_data` — retrieve actual (x, y) data points
  - `search_papers` — find papers by DOI/author/title/year
  - `get_paper_detail` — fetch one paper's samples and curves
  - `get_dataset_info` — report snapshot date, counts, license, freshness
- **Local-first ingestion pipeline**:
  - Daily public dataset snapshots downloaded from GitHub Releases (no connection to Starrydata production DB/API)
  - DuckDB-based ETL with atomic writes and manifest integrity checks
  - Idempotent updates (compares upstream `manifest.json`'s `db_snapshot` string to skip redundant downloads/rebuilds)
  - Graceful fallback on download/validation failure (continues serving the previous snapshot)
- **Dataset**: ~17,400 papers, 105,400 samples, 234,400 digitized property curves (CC BY 4.0). Verified by running a full real ingest and live tool calls against the actual production dataset, not just test fixtures.

**Real data-quality bugs found by ingesting the live production dataset** (not just curated test fixtures):
- **`papers.sid` is not globally unique**: two entirely unrelated papers (different DOI, different title) share `sid=18526` in the real dataset — an apparent upstream data-entry artifact. Removed the incorrect `PRIMARY KEY` constraint on `papers.sid`; `get_by_sid` now picks one row deterministically instead of crashing or depending on undefined SQL row order.
- **DuckDB `TIMESTAMP` columns round-trip as naive datetimes**: even though the ETL inserts timezone-aware UTC values, reading them back drops the tzinfo, which crashed `get_dataset_info`'s staleness comparison (`can't subtract offset-naive and offset-aware datetimes`) the first time it ran against a real, non-mocked snapshot. `DuckDBDatasetInfoRepository` now reattaches UTC on read.
- Both are covered by regression tests (`tests/infrastructure/test_duplicate_sid.py`).

**Quality & Testing**
- 127 tests, 98% overall coverage (domain/application layers effectively 100%)
- Domain layer: pure functions only (composition parser, citation formatter), zero external dependencies, tested without any I/O
- Application layer: use cases tested against in-memory fake repositories
- Infrastructure: integration tests against a DuckDB file built from real-shaped fixture CSVs, plus a full run against the live production dataset
- Interface: smoke tests for all 8 MCP tools via the real MCP `call_tool` path (in-process)
- All linting clean: `ruff check`, `ruff format`, `mypy --strict` (domain/application), `import-linter`

**UX/reliability fixes (owner-reported, 2026-08-16)**
- `ingest` was silent for the whole run, which read as a hang and led to a
  Ctrl+C that then made the *next* run fail with a raw DuckDB `Could not set
  lock on starrydata.duckdb.tmp.wal (Conflicting lock held by PID ...)`
  error. Fixed:
  - `ingest` now prints progress throughout: which file it's downloading and
    its size, and row counts as papers/samples/curves load (inserted in
    1,000-row chunks rather than one giant call).
  - Found and fixed a real performance bug along the way: indexes (including
    two `PRIMARY KEY`s) were being built *before* data load, so every insert
    chunk paid incremental index-maintenance cost — one 5,000-row chunk into
    `curves` could take 20-45s. Indexes now build once, after all data is
    loaded, which is both correct DB practice and dramatically faster.
  - Ctrl+C uses a cooperative flag checked between chunks
    (`infrastructure/ingestion/interrupt.py`), not a signal handler that
    tries to interrupt a DuckDB call mid-flight — deliberately, since
    relying on that behavior would mean depending on undocumented DuckDB
    internals. A second Ctrl+C force-quits immediately as an escape hatch.
  - An advisory lock (`cache_dir/ingest.lock`) makes "is another ingest
    really still running" an explicit, checkable fact. If held, `ingest`
    fails immediately with a clear message naming the holder's PID instead
    of a cryptic DuckDB error surfacing minutes later.
  - Once that lock is acquired, any leftover `.tmp`/`.tmp.wal`/staging files
    from a dead previous run are *guaranteed* stale and are cleaned up
    automatically with a friendly message — this is the actual root cause
    fix for the reported error (the old code cleaned up `.tmp` but never
    its `.wal` sidecar).
  - The live database was never at risk either way — the atomic
    build-then-rename design (already in place) means a crash mid-run
    always leaves the previous good snapshot untouched.
- Corrected the "how long does `ingest` take" estimate: an honest full run
  is 15-30 minutes (loading ~400k rows through `executemany` dominates —
  the ~57 MB download itself is quick), not the "5-10 minutes" originally
  guessed before this was actually measured against the live dataset.

**Known Limitations & Future Work**
- Composition parsing is best-effort (many samples have free-text descriptions; failures fall back to raw substring search)
- `sample_info` metadata is unstructured JSON with inconsistent key naming (expected from raw form inputs); whitelist approach applied with raw JSON fallback
- Data freshness check (24h stale flag) is logged but not auto-remedied; users must run `starrydata-mcp ingest` via cron/launchd
- No full-text search indexing yet (FTS extension reserved for future optimization)
- ETL bulk-load performance: rows are inserted via row-by-row `executemany`
  calls; DuckDB's native CSV/COPY ingestion path is substantially faster for
  this kind of bulk load but wasn't adopted here because the current
  approach also does per-row Python transforms (JSON parsing, composition
  parsing, computed columns) that a native-COPY approach would need to do
  in SQL instead — a bigger change than this bug-fix pass, worth a follow-up.

**Installation & Usage**
```bash
starrydata-mcp ingest  # Build/update local DuckDB from latest public snapshot
starrydata-mcp serve   # Start MCP server (stdio)
```

Register in MCP client config (Claude Desktop, Claude Code, etc.) and call `get_dataset_info` first to verify data freshness and retrieve the required citation.
