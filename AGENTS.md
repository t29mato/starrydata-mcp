# AGENTS.md

Instructions for AI coding agents working in this repository. (Claude-specific
workflow/reporting conventions live in [`CLAUDE.md`](CLAUDE.md); this file is
the general-purpose equivalent — the technical rules below apply regardless
of which agent is doing the work.)

## What this project is

`starrydata-mcp`: an MCP server exposing Starrydata's publicly distributed
materials-science dataset to AI agents, via a local DuckDB replica refreshed
daily from public snapshots. **Never connects to Starrydata's production
database or API** — see `docs/design/architecture.md` and
`docs/TECHNICAL_OVERVIEW.md` for the full rationale and architecture.

## Setup

```sh
uv sync --dev
```

## Build, test, lint

Run all of these before considering a change done; CI enforces the same set.

```sh
uv run pytest -q --cov-fail-under=85   # tests + coverage gate (repo is currently at 100%)
uv run ruff check .                     # lint
uv run ruff format .                    # format
uv run mypy                             # strict type check (domain + application layers)
uv run lint-imports                     # clean-architecture layering contracts
```

## Architecture rules (non-negotiable)

This codebase follows clean architecture with four layers under
`src/starrydata_mcp/`: `domain/` → `application/` → `infrastructure/` |
`interface/`. Dependency direction is enforced mechanically by
`import-linter` (see `[tool.importlinter]` in `pyproject.toml`), not just by
convention:

- `domain/` may import nothing outward — no `infrastructure`, `interface`,
  `application`, and no third-party packages (`duckdb`, `mcp`, `httpx`).
  Pure Python only.
- `application/` may import `domain` only — not `infrastructure` or
  `interface`.
- `infrastructure/` and `interface/` are siblings — neither imports the
  other. Both may import `domain`.
- `cli.py` (composition root) sits outside this layering and is the one
  place infrastructure/interface classes get wired together.

If a change would violate one of these, the design is wrong, not the
contract — restructure the change rather than loosening `pyproject.toml`.

## Test-first

Write the test before the implementation. Tests are organized by layer
(`tests/domain/`, `tests/application/`, `tests/infrastructure/`,
`tests/interface/`) mirroring `src/`. Fixtures under `tests/fixtures/raw/`
are shaped like the *real* upstream CSVs (same headers, quoting, BOM) —
prefer extending those over inventing new synthetic shapes, and regenerate
them with `tests/fixtures/build_fixture_csvs.py` if the shape needs to
change.

When something surprising turns up in real data (see `docs/design/
architecture.md` §5 and `docs/TECHNICAL_OVERVIEW.md` §6 for two examples:
non-unique `papers.sid`, DuckDB's naive-datetime round-trip), add a
regression test that encodes the real example, not just an abstract case.

## LLMO (this is product surface, not an afterthought)

MCP tool `description`s in `src/starrydata_mcp/interface/mcp_server.py` are
read by AI agents to decide how to call each tool — get them wrong and the
tool gets misused or ignored. When touching a tool's signature or behavior,
update its description in the same change, and keep the "search → narrow →
fetch" three-tier pattern intact (light summaries first; only
`get_curve_data` returns raw point arrays).

## Branch / PR

Do not push directly to `main`. Feature branch → PR. See `CLAUDE.md` for
this repository's specific merge/release process.
