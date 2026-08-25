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
- 163 tests, 100% coverage (see "Quality follow-up" below for how the last
  couple of percentage points were closed)
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

**Quality follow-up (while Issue #15's publish decision is pending, 2026-08-21)**
- Closed the remaining coverage gap (98% -> 100%): added real regression
  tests for edge cases that were previously only implicit — the hot-swap
  path in `DuckDBConnectionProvider` (picking up a new DB file without a
  restart), `get_dataset_info` against a null `db_snapshot` and against a
  DB with no `dataset_meta` row at all, the cooperative-SIGINT second-press
  force-quit escape hatch, a couple of citation-formatting edge cases
  (author with only a given or only a family name), and the CLI's
  `__main__` entrypoint (via a real subprocess). Two lines of genuinely
  trivial entrypoint boilerplate (`def main(): app()` and the
  `if __name__ == "__main__"` guard) are `# pragma: no cover` with a
  comment explaining why, rather than force-tested.
- LLMO assets audited and filled in: `llms.txt` (repo root, for any LLM/
  agent trying to understand the project), `AGENTS.md` (generic
  build/test/lint/architecture-rules guide for any coding agent, alongside
  the Claude-specific `CLAUDE.md`), and a Claude Code project skill at
  `.claude/skills/starrydata-mcp/SKILL.md` teaching effective use of the 8
  MCP tools (search -> narrow -> fetch, when to call `list_properties`
  first, etc.). README's opening one-liner was already present.
- Long-running-operation concerns written up in
  `docs/OPERATIONAL_CONCERNS.md`: disk usage doesn't grow unboundedly
  (fixed-path files, guaranteed cleanup), but a full ingest run temporarily
  needs ~500-550MB on top of the live DB's own footprint; and upstream CSV
  schema changes are handled inconsistently — optional fields degrade
  silently to empty, but required fields (`SID`, `sample_id`) and
  `manifest.json`'s keys raise a raw `KeyError` (safely — nothing gets
  corrupted — but with an unhelpful message). Neither is an active bug;
  both are recorded as follow-up candidates.

**Remote MCP server support (owner request via HQ, 2026-08-25)**
- `starrydata-mcp serve --http :7860` starts the same 8 tools over
  streamable-HTTP instead of stdio (stdio remains the default — nothing
  changes for existing local/Claude Desktop/Code users). Address syntax:
  `--http :7860` (all interfaces), `--http 127.0.0.1:9000`, or a bare port.
- `/health` endpoint reports whether the local DuckDB is actually queryable
  (not just "the process is up") — 200 with snapshot date/totals/staleness,
  or 503 if `dataset_meta` is missing/empty.
- Simple per-IP rate limiting (`infrastructure`-free, plain ASGI middleware
  — deliberately not Starlette's `BaseHTTPMiddleware`, which buffers whole
  responses and fights streamable-HTTP's chunked responses), default 60
  requests/60s/IP, tunable via `STARRYDATA_MCP_RATE_LIMIT_MAX` /
  `STARRYDATA_MCP_RATE_LIMIT_WINDOW_SECONDS`. Not meant to stop a
  determined abuser — just to keep one client from accidentally exhausting
  a free-tier deployment.
- Server instructions (shown to any connecting agent) now explicitly state
  the server is read-only and that a public deployment may be rate-limited.
- `Dockerfile` + `.dockerignore` for Hugging Face Spaces (Docker SDK):
  bakes a fresh `ingest` into the image at *build* time (non-root user,
  port 7860) so the container answers `/health` immediately on boot
  instead of spending 15-30 minutes ingesting before serving a single
  request. Deployment itself (creating the Space, pushing the image) is
  intentionally not done by this change — see
  `docs/deploy/huggingface-spaces.md` for the handoff procedure to the
  owner, including the "rebuild to refresh the snapshot" operational note
  (this image does not self-refresh; see the Known Limitations below).
- README: "Connecting to a remote server" section with the exact
  `claude mcp add --transport http` command and claude.ai Connectors steps
  (placeholder URL — filled in once actually deployed).
- Verified for real, not just unit-tested: `scripts/verify_http_server.py`
  starts the real HTTP server as a subprocess against the real ~193MB
  production DuckDB, connects with the real `mcp.client.Client` (streamable-
  HTTP), and calls all 8 tools — all passed. A fixture-DB equivalent
  (`tests/interface/test_http_server_e2e.py`) runs the same real-subprocess/
  real-client pattern in CI. 181 tests total (was 163), 100% coverage
  maintained.

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
- The HF Spaces `Dockerfile` bakes in a snapshot at build time and does not
  refresh itself — picking up a new daily snapshot means rebuilding the
  Space (manually or on a schedule the owner sets up outside this repo).
  Not automated here; see `docs/deploy/huggingface-spaces.md` §6.

**Installation & Usage**
```bash
starrydata-mcp ingest              # Build/update local DuckDB from latest public snapshot
starrydata-mcp serve                # Start MCP server (stdio, for local clients)
starrydata-mcp serve --http :7860  # ...or streamable-HTTP, for a self-hosted/remote deployment
```

Register in MCP client config (Claude Desktop, Claude Code, etc.) and call `get_dataset_info` first to verify data freshness and retrieve the required citation.
