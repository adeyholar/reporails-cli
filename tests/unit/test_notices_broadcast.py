"""The shared broadcast fixture: each case's delivered list decodes into the notices the client shows."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import pytest
from rich.console import Console

from reporails_cli.core.platform.adapters.notices_wire import notices_from_header
from reporails_cli.core.platform.dto.diagnostics import Notice
from reporails_cli.formatters.text.notices import print_notices

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "notices_broadcast.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


def _header(entries: list[dict]) -> str:
    return base64.urlsafe_b64encode(json.dumps(entries).encode("utf-8")).decode("ascii").rstrip("=")


def _expected(entry: dict) -> Notice:
    return Notice(
        id=entry["id"],
        level=entry["level"],
        text=entry["text"],
        url=entry.get("url", ""),
        kind="promo" if entry.get("kind") == "promo" else "notice",
    )


@pytest.mark.unit
@pytest.mark.subsys_cli_ux
@pytest.mark.parametrize("case", CASES, ids=[f"{c['caller']}-{c['date']}" for c in CASES])
def test_delivered_entries_decode_to_matching_notices(case: dict) -> None:
    got = notices_from_header(_header(case["delivered"]))
    assert got == tuple(_expected(e) for e in case["delivered"])


@pytest.mark.unit
@pytest.mark.subsys_cli_ux
def test_entries_without_a_kind_decode_and_render_as_plain_notices() -> None:
    entries = [
        {"id": "a", "level": "info", "text": "One"},
        {"id": "b", "level": "warn", "text": "Two", "url": "https://e.test"},
    ]
    got = notices_from_header(_header(entries))
    assert [n.kind for n in got] == ["notice", "notice"]
    buf = io.StringIO()
    print_notices(Console(file=buf, force_terminal=True, width=80), got, ascii_mode=False)
    assert "One" in buf.getvalue()
    assert "Two" in buf.getvalue()
    assert "─" not in buf.getvalue()
