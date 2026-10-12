"""The lines that name the checks that did not finish."""

from __future__ import annotations

from collections.abc import Iterable

from rich.console import Console
from rich.markup import escape


def group_not_evaluated(pairs: Iterable[tuple[str, str]]) -> list[tuple[str, list[str]]]:
    """The `(rule id, file)` pairs as `(file, [rule ids])`, files and rules in first-seen order."""
    by_file: dict[str, list[str]] = {}
    for rule, file in pairs:
        rules = by_file.setdefault(file, [])
        if rule not in rules:
            rules.append(rule)
    return list(by_file.items())


def not_evaluated_sentence(file: str, rules: list[str]) -> str:
    """`Not evaluated in <file>: <rules> — the check did not finish in time`, plain text."""
    return (
        f"Not evaluated in {file}: {', '.join(rules)} — "
        f"{'the check' if len(rules) == 1 else 'these checks'} did not finish in time"
    )


def not_evaluated_lines(pairs: Iterable[tuple[str, str]]) -> list[str]:
    """One dim line per file naming its `(rule id, file)` pairs, in first-seen order; empty when there are none."""
    return [f"[dim]{escape(not_evaluated_sentence(file, rules))}[/dim]" for file, rules in group_not_evaluated(pairs)]


def print_not_evaluated(console: Console, pairs: Iterable[tuple[str, str]]) -> None:
    """Print the not-evaluated lines under the run's results; nothing when every check finished."""
    lines = not_evaluated_lines(pairs)
    if lines:
        console.print()
        for line in lines:
            console.print(f"  {line}", soft_wrap=True)
