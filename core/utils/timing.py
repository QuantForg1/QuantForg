"""Timing utilities for measuring elapsed durations."""

from __future__ import annotations

import time
from types import TracebackType


class Timer:
    """Context manager that records wall-clock elapsed time in milliseconds.

    Example
    -------
    >>> with Timer() as t:
    ...     do_work()
    >>> print(t.elapsed_ms)
    """

    def __init__(self) -> None:
        self._start: float = 0.0
        self._end: float = 0.0

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._end = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        """Elapsed time in milliseconds since enter."""
        end = self._end if self._end else time.perf_counter()
        return (end - self._start) * 1000.0
