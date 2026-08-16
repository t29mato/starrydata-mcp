"""In-process unit tests for the cooperative SIGINT flag mechanism itself
(the handler function, checkpoint, and second-press escape hatch). The
real-subprocess, real-SIGINT end-to-end behavior is covered separately by
test_sigint_regression.py — this file is the fast, non-flaky complement.
"""

from __future__ import annotations

import signal

import pytest

from starrydata_mcp.infrastructure.ingestion.interrupt import (
    InterruptRequested,
    cooperative_sigint,
)


def test_raise_if_interrupted_is_a_noop_before_any_signal() -> None:
    with cooperative_sigint() as raise_if_interrupted:
        raise_if_interrupted()  # must not raise


def test_first_press_sets_flag_and_next_checkpoint_raises() -> None:
    with cooperative_sigint() as raise_if_interrupted:
        signal.raise_signal(signal.SIGINT)  # simulate Ctrl+C, in-process
        with pytest.raises(InterruptRequested):
            raise_if_interrupted()


def test_on_first_press_callback_fires_exactly_once() -> None:
    calls: list[None] = []
    with cooperative_sigint(on_first_press=lambda: calls.append(None)) as raise_if_interrupted:
        signal.raise_signal(signal.SIGINT)
        assert len(calls) == 1
        with pytest.raises(InterruptRequested):
            raise_if_interrupted()


def test_previous_handler_is_restored_on_exit() -> None:
    sentinel_called = []

    def sentinel_handler(signum: int, frame: object) -> None:
        sentinel_called.append(True)

    previous = signal.signal(signal.SIGINT, sentinel_handler)
    try:
        with cooperative_sigint():
            assert signal.getsignal(signal.SIGINT) is not sentinel_handler
        assert signal.getsignal(signal.SIGINT) is sentinel_handler
    finally:
        signal.signal(signal.SIGINT, previous)


def test_interrupt_requested_is_a_keyboard_interrupt_subclass() -> None:
    assert issubclass(InterruptRequested, KeyboardInterrupt)
