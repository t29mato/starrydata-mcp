# starrydata-mcp

**Search and retrieve digitized materials-science data from [Starrydata](https://starrydata.nims.go.jp/) via AI agents.**

Starrydata is a database of property measurements (curves) extracted from published papers, covering thermoelectric, battery, magnetic, dielectric, and other advanced materials. This MCP server lets AI agents search that data by composition, elements, physical properties, and research domain — all against a local DuckDB replica refreshed daily from Starrydata's public dataset, with no connection to its production systems.

Status: **Pre-release, under active development**. See [`docs/design/architecture.md`](docs/design/architecture.md) for the full architecture and design rationale.

## Installation

```bash
pip install starrydata-mcp   # not yet published to PyPI
```

## Quick start

```bash
# Step 1: Download the latest public dataset snapshot and build local DuckDB.
# The ~57 MB download itself is quick; loading the ~400k rows is the slow
# part, so a full run typically takes 15-30 minutes. It prints progress as
# it goes (which file it's downloading, how many rows loaded so far), and
# Ctrl+C is safe at any point: partial files are cleaned up automatically,
# and the live database (if you already have one from a previous run) is
# never touched until the new build finishes — it's swapped in atomically
# at the very end.
starrydata-mcp ingest

# Step 2: Start the MCP server
starrydata-mcp serve
```

Register `starrydata-mcp serve` as an MCP server in your agent's config (e.g., Claude Desktop, Claude Code):

```json
{
  "mcpServers": {
    "starrydata": {
      "command": "starrydata-mcp",
      "args": ["serve"]
    }
  }
}
```

The server will serve stdio by default. See [`docs/design/architecture.md#2-日次取得--ローカルdb変換パイプライン`](docs/design/architecture.md) for details on how data ingestion works and how to set up a daily refresh schedule.

To self-host over HTTP instead of stdio (e.g. behind your own reverse proxy), use `starrydata-mcp serve --http :7860` — see [`docs/deploy/huggingface-spaces.md`](docs/deploy/huggingface-spaces.md) for a ready-to-use `Dockerfile` and deployment walkthrough (Hugging Face Spaces' free tier).

## Connecting to a remote server (no local setup)

Running `ingest` locally (15-30 minutes, ~190 MB) is a real barrier for a
researcher who just wants to ask a question. A hosted, read-only instance
removes that: connect an MCP client straight to it over HTTP, no install
required.

> **Status**: the hosted instance isn't live yet — deployment is a separate,
> explicit step (see [`docs/deploy/huggingface-spaces.md`](docs/deploy/huggingface-spaces.md)).
> Once it is, replace `<space-url>` below with the real URL.

**Claude Code:**

```sh
claude mcp add --transport http starrydata https://<space-url>/mcp
```

**claude.ai (web) — Settings → Connectors → Add custom connector:**

Enter `https://<space-url>/mcp` as the remote MCP server URL and confirm.
(Anthropic's UI wording for this may shift over time; look for "Connectors"
or "Integrations" under Settings if it's moved.)

The remote server is **read-only** and rate-limited per client — see its
`/health` endpoint for the current data snapshot date, and
[Data source](#data-source) below for the license/citation, which apply
identically whether you run it yourself or use a hosted instance.

## Tools

The server exposes 8 tools, following a **search → narrow → fetch** three-tier pattern to keep AI agent context small:

| Tool | Purpose |
|---|---|
| **`search_materials`** | Find samples by chemical composition, constituent elements, or research domain (thermoelectric/battery/magnetic/dielectric). Returns lightweight summaries (sample_uid, composition, list of measured properties). |
| **`get_sample_detail`** | Fetch full metadata for one sample: composition, fabrication/measurement details, and index of all property curves measured on it. |
| **`list_properties`** | Browse the vocabulary of measured properties in Starrydata (Temperature vs Seebeck coefficient, ZT, thermal conductivity, etc.), ranked by frequency. Use this to find exact property names before calling `search_curves`. |
| **`search_curves`** | Search for property-vs-property curves by property pair, composition/elements, x-axis numeric range, and research domain. Returns summaries with curve_id, point count, observed x/y ranges. |
| **`get_curve_data`** | Fetch the actual (x, y) data points for one or more curves by curve_id, with axis units and source citation. Call after narrowing with `search_curves`. |
| **`search_papers`** | Find papers by DOI, author, title keyword, publication year, or research domain. Each result includes a formatted citation. |
| **`get_paper_detail`** | Fetch one paper's full record by sid (from `search_papers` results): citation, and all samples and curves extracted from that paper. |
| **`get_dataset_info`** | Report the local snapshot date, record counts (papers/samples/curves), license (CC BY 4.0), citation, and data freshness. Call once at session start. |

## Data source

- **Source**: [Starrydata2](https://starrydata.nims.go.jp/) public dataset, distributed daily via [GitHub Releases](https://github.com/starrydata/starrydata_datasets/releases) as gzip CSV files (~57 MB compressed, updated ~03:00 JST).
- **Scope**: ~17,400 papers, 105,400 samples, 234,400 digitized property curves (thermoelectric materials dominate the dataset).
- **Local DB**: DuckDB file (~190 MB after a full ingest), built once per ingest run. No connection to Starrydata's production database or API.
- **License**: Data is CC BY 4.0. See [Data citation](#data-citation) below.

## Data citation

When you use this data, cite:

> Katsura, Kumagai, Mato, Takada, Ando, Fujita, Hosono, Koyama, Mudasar, Phuong, Saito, Sakamoto, Tanaka, Yana, Kimura, Tsuda, Demura. *Starrydata: from published plots to shared materials data.* Science and Technology of Advanced Materials: Methods, 5(1), 2506976 (2025). https://doi.org/10.1080/27660400.2025.2506976

For more details on the dataset's license and attribution requirements, see [`docs/design/architecture.md#13-ライセンス実データで確認`](docs/design/architecture.md#13-ライセンス実データで確認).

## License

- **Code**: MIT
- **Data served**: CC BY 4.0 (see citation above)

## Contributing

See [`AGENTS.md`](./AGENTS.md) for build/test/lint commands and architecture rules (any coding agent), or [`CLAUDE.md`](./CLAUDE.md) for this repository's specific workflow.
