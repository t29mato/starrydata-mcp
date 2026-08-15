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

**Known Limitations & Future Work**
- Composition parsing is best-effort (many samples have free-text descriptions; failures fall back to raw substring search)
- `sample_info` metadata is unstructured JSON with inconsistent key naming (expected from raw form inputs); whitelist approach applied with raw JSON fallback
- Data freshness check (24h stale flag) is logged but not auto-remedied; users must run `starrydata-mcp ingest` via cron/launchd
- No full-text search indexing yet (FTS extension reserved for future optimization)

**Installation & Usage**
```bash
starrydata-mcp ingest  # Build/update local DuckDB from latest public snapshot
starrydata-mcp serve   # Start MCP server (stdio)
```

Register in MCP client config (Claude Desktop, Claude Code, etc.) and call `get_dataset_info` first to verify data freshness and retrieve the required citation.
