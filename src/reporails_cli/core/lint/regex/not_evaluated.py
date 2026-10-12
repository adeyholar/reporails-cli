"""Checks that did not finish: a pattern search that ran out of time leaves its check unevaluated.

A scope collects the `(rule id, file)` pairs of those checks while it is open; outside a scope
nothing is recorded.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_collector: ContextVar[list[tuple[str, str]] | None] = ContextVar("not_evaluated_collector", default=None)


class PatternTimeoutError(Exception):
    """A pattern search did not finish within its time limit."""


def rule_id_of(check_id: str) -> str:
    """`CORE.C.0037.has-multiple-sections` -> `CORE:C:0037`; an id with fewer than three parts is returned as is."""
    parts = check_id.split(".")
    return ":".join(parts[:3]) if len(parts) >= 3 else check_id


def record_not_evaluated(rule_id: str, file: str) -> None:
    """Add `(rule_id, file)` to the open scope's list; do nothing when no scope is open."""
    bucket = _collector.get()
    if bucket is not None:
        bucket.append((rule_id, file))


@contextmanager
def not_evaluated_scope() -> Iterator[list[tuple[str, str]]]:
    """Open a scope and yield the list that collects the `(rule id, file)` pairs left unevaluated inside it."""
    bucket: list[tuple[str, str]] = []
    token = _collector.set(bucket)
    try:
        yield bucket
    finally:
        _collector.reset(token)
