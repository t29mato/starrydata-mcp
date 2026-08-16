"""Cooperative Ctrl+C handling for the ingest pipeline.

Bug fix (2026-08-16, reported by the owner): part of fixing "ingest looked
hung, Ctrl+C didn't seem to do anything" (see `etl.py`'s and `schema.py`'s
comments for the other part — a real performance issue in how/when indexes
were built that made individual insert chunks slow enough to look hung on
their own).

The obvious approach — reassert Python's default SIGINT handler
(`signal.default_int_handler`) so Ctrl+C raises `KeyboardInterrupt`
immediately, including while a DuckDB query is in flight — does work (confirmed
in isolated testing: DuckDB cleanly raises "Query interrupted" from the
call in progress). This module deliberately doesn't rely on that anyway:
asking a C extension to unwind mid-call in response to an async signal is
exactly the kind of behavior that's easy to get right today and break
silently on a future DuckDB version, since it isn't a documented, load-bearing
part of DuckDB's Python API.

Instead, the SIGINT handler installed by `cooperative_sigint` only ever
*sets a flag* — it never raises anything itself, so a DuckDB call in flight
is never asked to abort mid-query. Callers check the flag cooperatively,
via `raise_if_interrupted()`, at points that are already safe (after each
`executemany` chunk in `etl.py`, after each downloaded file in
`downloader.py` — both go through `pipeline.py`'s `on_progress` callback,
which is where the check lives). `KeyboardInterrupt` is therefore only ever
raised from plain Python code. Worst-case latency is one chunk's or one
file download's duration — bounded by `etl._CHUNK_SIZE` — a world away from
the reported 8-minute silent hang.

A second Ctrl+C bypasses all of this and quits immediately via the OS
default, as an escape hatch in case no checkpoint is ever reached.
"""

from __future__ import annotations

import contextlib
import signal
from collections.abc import Callable, Iterator


class InterruptRequested(KeyboardInterrupt):
    """Raised cooperatively, from plain Python code, once a checkpoint sees
    that Ctrl+C was pressed. A `KeyboardInterrupt` subclass so existing
    `except KeyboardInterrupt` handling (pipeline.py, cli.py) needs no
    special-casing."""


@contextlib.contextmanager
def cooperative_sigint(
    on_first_press: Callable[[], None] | None = None,
) -> Iterator[Callable[[], None]]:
    """Context manager yielding `raise_if_interrupted()`.

    Call the yielded function at safe checkpoints; it raises
    `InterruptRequested` if Ctrl+C was pressed since the last check.
    """
    state = {"requested": False}

    def handler(signum: int, frame: object) -> None:
        if state["requested"]:
            # Second press: no more cooperation, quit right now.
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            signal.raise_signal(signal.SIGINT)
            return
        state["requested"] = True
        if on_first_press is not None:
            on_first_press()

    def raise_if_interrupted() -> None:
        if state["requested"]:
            raise InterruptRequested

    previous_handler = signal.signal(signal.SIGINT, handler)
    try:
        yield raise_if_interrupted
    finally:
        signal.signal(signal.SIGINT, previous_handler)
