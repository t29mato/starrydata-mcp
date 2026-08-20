---
name: starrydata-mcp
description: Use when the user asks about materials-science property data — thermoelectric, battery, magnetic, or dielectric materials, chemical composition/element search, or literature-derived measurement curves (Seebeck coefficient, ZT, thermal conductivity, discharge capacity, dielectric permittivity, etc.) — and the starrydata-mcp MCP server's tools are available. Also use when setting up, troubleshooting, or explaining the starrydata-mcp server itself (ingest/serve, its 8 tools, or its data source).
---

# starrydata-mcp

Guidance for using the `starrydata-mcp` MCP server's tools effectively, and
for setting it up when its tools aren't registered yet.

## If the tools aren't available yet

The user needs to install and register the server first:

```sh
starrydata-mcp ingest   # downloads the public dataset and builds a local DuckDB file — 15-30 min on a full run
starrydata-mcp serve    # starts the MCP server (stdio)
```

Then register `starrydata-mcp serve` in the client's MCP config (see the
project README for the exact JSON). Don't try to work around a missing
server by fetching Starrydata data another way (e.g. scraping
starrydata.nims.go.jp) — the whole point of this project is to query a
locally-vetted, licensed, offline replica.

## If the tools are available

1. **Call `get_dataset_info` once at the start of the session.** It reports
   the local snapshot's date, record counts, license (CC BY 4.0), and the
   citation string to use if you quote any data back to the user. If
   `is_stale` is true, mention that the data may be more than a day old.

2. **Search before you fetch — don't guess curve_ids.** Tools follow a
   search → narrow → fetch pattern specifically so you don't pull large
   point arrays into context before you need them:
   - `search_materials` / `search_curves` / `search_papers` /
     `list_properties` return lightweight summaries only.
   - `get_sample_detail` / `get_paper_detail` return one record's full
     metadata plus an index of its curves (still no raw point arrays).
   - `get_curve_data` is the only tool that returns actual (x, y) arrays —
     call it last, with curve_ids you got from `search_curves` or
     `get_sample_detail`, and keep requests to roughly 20 ids or fewer.

3. **Call `list_properties` before guessing a property name.** `prop_x`/
   `prop_y` values (e.g. "Seebeck coefficient", "ZT", "Thermal
   conductivity") are extracted verbatim from plot axis labels in the
   source papers, so they have some spelling variation. Passing a guessed
   name straight to `search_curves` will just return zero results —
   `list_properties` shows the real vocabulary, ranked by frequency,
   optionally scoped to a `project` (e.g. "ThermoelectricMaterials",
   "BatteryMaterials", "MagneticMaterials", "DielectricMaterials").

4. **Prefer `elements` over `composition` substring matching when
   stoichiometry doesn't matter.** `composition` on `search_materials`/
   `search_curves` is a case-insensitive substring match against the raw
   formula string (e.g. "Bi2Te3"); if the user cares about "does it contain
   bismuth and tellurium" rather than an exact formula, pass
   `elements: ["Bi", "Te"]` instead (AND semantics on constituent
   elements).

5. **Cite the source paper.** Every curve/sample carries back to a DOI and
   a formatted citation string (via `get_curve_data`, `get_sample_detail`,
   `get_paper_detail`, or `search_papers`) — surface it when reporting
   specific numeric values to the user, not just the dataset-level citation
   from `get_dataset_info`.

## Example flow

> "What's the Seebeck coefficient vs temperature for Bi2Te3-based
> thermoelectrics?"

1. `list_properties(project="ThermoelectricMaterials")` → confirm the exact
   property-pair string (likely `"Temperature"` / `"Seebeck coefficient"`).
2. `search_curves(prop_x="Temperature", prop_y="Seebeck coefficient",
   elements=["Bi","Te"], limit=10)` → get candidate curve summaries.
3. `get_curve_data(curve_ids=[...])` on the ones that look relevant (check
   `point_count`/`x_min`/`x_max` in the summaries first) → get the actual
   data points, with citations.
