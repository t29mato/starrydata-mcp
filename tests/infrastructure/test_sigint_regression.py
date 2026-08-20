"""Regression test for the 2026-08-16 owner-reported bug: `starrydata-mcp
ingest` looked hung and Ctrl+C appeared to do nothing.

Two distinct things were going on, both found by real-subprocess testing
(a mocked `raise KeyboardInterrupt` can't catch either of these):

  1. `executemany` inserts into `curves` (two `DOUBLE[]` + one `VARCHAR[]`
     column) cost several milliseconds per row, and building indexes
     *before* loading made every chunk's cost far worse on top of that
     (see schema.py's `INDEXES_DDL` comment — indexes now build once, after
     loading). A single 5,000-row chunk could legitimately take 20-45s.
     What first looked like "Ctrl+C is flaky, sometimes it just hangs" was
     actually deterministic: the interrupt was queued correctly and landed
     at the next chunk boundary every time, but a too-short test timeout
     (chosen before this cost was known) sometimes wasn't long enough to
     see it land. `_CHUNK_SIZE` is now smaller (1,000) partly to bound this
     latency better.
  2. Interruption itself uses `interrupt.cooperative_sigint`, which never
     asks DuckDB to abort a query mid-flight (only sets a flag, checked
     between chunks) — not because that was proven unsafe, but because
     relying on undocumented internals of how a specific DuckDB version
     reacts to an async signal into its C code is fragile to build a
     product on, versus a plain flag check in our own Python code.

This test spawns a real subprocess, opens a real DuckDB connection via
`build_database`, and sends a real `SIGINT`, repeated a few times.
"""

from __future__ import annotations

import csv
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

SRC_DIR = Path(__file__).parents[2] / "src"
FIXTURES = Path(__file__).parent.parent / "fixtures" / "raw"

# Mirrors cli.py's `ingest` command: cooperative_sigint + a checkpoint in
# on_progress, wrapping the real build_database. Kept import-only (no
# network) so this test doesn't depend on GitHub Releases being reachable.
_BUILD_SCRIPT = """
import sys
sys.path.insert(0, {src_dir!r})
from datetime import UTC, datetime
from pathlib import Path
from starrydata_mcp.infrastructure.ingestion.etl import DatasetMetaInput, build_database
from starrydata_mcp.infrastructure.ingestion.interrupt import cooperative_sigint

with cooperative_sigint() as raise_if_interrupted:
    def on_progress(message):
        print(message, flush=True)
        raise_if_interrupted()

    build_database(
        papers_csv=Path({papers_csv!r}),
        samples_csv=Path({samples_csv!r}),
        curves_csv=Path({curves_csv!r}),
        meta=DatasetMetaInput(
            db_snapshot=None, generated_at=datetime.now(UTC),
            papers=2, figures=0, samples=0, curves=30000,
            license="", citation="", source_url="",
        ),
        dest_path=Path({dest_path!r}),
        on_progress=on_progress,
    )
    print("FINISHED WITHOUT INTERRUPT", flush=True)
"""


def _write_large_curves_csv(path: Path, n_rows: int) -> None:
    """A big-enough curves.csv that loading it takes a little while, long
    enough to reliably land a SIGINT mid-build."""
    header = [
        "SID",
        "DOI",
        "composition",
        "sample_id",
        "figure_id",
        "figure_name",
        "prop_x",
        "prop_y",
        "unit_x",
        "unit_y",
        "x",
        "y",
        "created_at",
        "updated_at",
        "project_names",
        "comments",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        row = [
            "6",
            "10.1/x",
            "Bi2Te3",
            "1",
            "1",
            "1",
            "Temperature",
            "ZT",
            "K",
            "-",
            "[300.0,400.0]",
            "[0.1,0.2]",
            "",
            "",
            '["ThermoelectricMaterials"]',
            "",
        ]
        for _ in range(n_rows):
            writer.writerow(row)


def _run_once(tmp_path: Path, run_index: int) -> tuple[str, str]:
    curves_csv = tmp_path / f"curves_{run_index}.csv"
    _write_large_curves_csv(curves_csv, 30_000)
    dest_path = tmp_path / f"starrydata_{run_index}.duckdb"

    script = _BUILD_SCRIPT.format(
        src_dir=str(SRC_DIR),
        papers_csv=str(FIXTURES / "papers.csv"),
        samples_csv=str(FIXTURES / "samples.csv"),
        curves_csv=str(curves_csv),
        dest_path=str(dest_path),
    )

    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,  # own process group, like a real terminal job
    )
    try:
        time.sleep(0.4)
        os.killpg(proc.pid, signal.SIGINT)
        try:
            # 25s, not ~5s (chunk size 1,000 * ~5ms/row): on a loaded CI/dev
            # machine the first executemany call (one-time query-plan
            # compilation on top of the per-row cost) has been observed to
            # take noticeably longer than later chunks. This margin is
            # about ruling out an indefinite hang, not measuring latency —
            # keep it generous rather than chase machine-dependent timing.
            stdout, stderr = proc.communicate(timeout=25)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
            raise AssertionError(
                f"run {run_index}: build_database did not stop within 25s of "
                f"SIGINT — this is exactly the reported hang.\nstdout:\n{stdout}"
                f"\nstderr:\n{stderr}"
            ) from None
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()

    return stdout, stderr


def test_sigint_reliably_interrupts_build_database_across_repeated_runs(
    tmp_path: Path,
) -> None:
    # Run a few times: the naive first attempt (default_int_handler,
    # interrupting DuckDB mid-query) *looked* flaky — some runs "hung" past
    # a short timeout — but turned out to be a deterministic per-chunk cost
    # colliding with too-short a timeout, not true nondeterminism (see
    # module docstring). A couple of repeats is enough to guard against a
    # regression back to that state.
    for i in range(3):
        stdout, stderr = _run_once(tmp_path, i)
        assert "FINISHED WITHOUT INTERRUPT" not in stdout, (
            f"run {i}: process ran to completion instead of being interrupted.\nstdout:\n{stdout}"
        )
        assert "InterruptRequested" in stderr or "KeyboardInterrupt" in stderr, (
            f"run {i}: expected an InterruptRequested/KeyboardInterrupt traceback.\n{stderr}"
        )
