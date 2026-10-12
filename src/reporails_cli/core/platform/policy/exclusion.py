"""Which paths a folder exclusion leaves out."""

from __future__ import annotations

from collections.abc import Iterable


def excluded_by_name(parts: Iterable[str], exclude_dirs: frozenset[str]) -> bool:
    """True when any part of a path is named in `exclude_dirs`, so a name matches a folder at any depth."""
    return any(part in exclude_dirs for part in parts)
