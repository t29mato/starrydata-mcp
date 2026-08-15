# starrydata-mcp

An MCP server that lets AI agents search and retrieve materials-science data (papers, samples, and digitized property curves) from [Starrydata2](https://starrydata.nims.go.jp/)'s publicly distributed dataset (CC BY 4.0), via a local DuckDB replica refreshed daily from public snapshots — no connection to Starrydata's production database or API.

Status: pre-release, under active development. See [`docs/design/architecture.md`](docs/design/architecture.md) for the full design.

## Install

```sh
pip install starrydata-mcp   # not yet published
```

## Usage

```sh
starrydata-mcp ingest   # download the latest public dataset snapshot and build the local DuckDB file
starrydata-mcp serve    # start the MCP server (stdio) against that local DB
```

Register `starrydata-mcp serve` as an MCP server in your agent's config (e.g. Claude Desktop / Claude Code).

## License

Code: MIT. Data served by this tool is Starrydata2's public dataset, licensed CC BY 4.0 — see [`docs/design/architecture.md#13-ライセンス実データで確認`](docs/design/architecture.md) for the citation to include when you use it.
