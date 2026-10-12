"""Text imported from a file the run left out still counts; the Excluded line, JSON and MCP view say so."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from reporails_cli.core.discovery.exclusions import load_run_exclusions
from reporails_cli.core.discovery.features import detect_features_filesystem
from reporails_cli.core.pipeline.assemble import AssembleInputs, _imports_left_out
from reporails_cli.core.platform.runtime.merger import CombinedResult
from reporails_cli.formatters import json as json_formatter
from reporails_cli.formatters import mcp_view
from reporails_cli.formatters.text.display_constants import excluded_phrase

CLAUSE = "imported text in checked files still counts"


def _inputs(root: Path, imported_from: str | None) -> AssembleInputs:
    atom = SimpleNamespace(file_path=str(root / "CLAUDE.md"), imported_from=imported_from)
    return AssembleInputs(
        m_findings=[],
        content_findings=[],
        client_findings=[],
        ruleset_map=SimpleNamespace(atoms=[atom]),
        scan_root=root,
        filter_agents=None,
        effective_agent="claude",
        lint_result=None,
        alias_fn=lambda _r: set(),
    )


@pytest.mark.unit
@pytest.mark.subsys_lint
@pytest.mark.parametrize("config", ["", "generic_scanning: true\n"], ids=["scanning-off", "scanning-on"])
def test_import_into_a_left_out_folder_sets_the_flag(tmp_path: Path, config: str) -> None:
    (tmp_path / ".ails").mkdir()
    (tmp_path / ".ails" / "config.yml").write_text(config or "{}\n", encoding="utf-8")
    left_out = load_run_exclusions(tmp_path, ["ext"], None)
    assert _imports_left_out(_inputs(tmp_path, "ext/notes.md"), left_out)
    assert not _imports_left_out(_inputs(tmp_path, "docs/notes.md"), left_out)
    assert not _imports_left_out(_inputs(tmp_path, None), left_out)
    assert not _imports_left_out(_inputs(tmp_path, "ext/notes.md"), None)


@pytest.mark.unit
@pytest.mark.subsys_lint
def test_text_line_ends_with_the_clause_only_when_an_import_crosses() -> None:
    assert excluded_phrase(["ext"], [], imported_counted=True).endswith(f"; {CLAUSE}")
    assert "the score covers the rest; imported" in excluded_phrase(["ext"], [], imported_counted=True)
    assert CLAUSE not in excluded_phrase(["ext"], [])
    assert excluded_phrase([], [], imported_counted=True) == ""


@pytest.mark.unit
@pytest.mark.subsys_lint
def test_json_excluded_object_carries_the_flag() -> None:
    on = json_formatter.format_combined_result(CombinedResult(excluded_dirs=("ext",), excluded_imported=True))
    off = json_formatter.format_combined_result(CombinedResult(excluded_dirs=("ext",)))
    assert on["excluded"] == {"dirs": ["ext"], "files": [], "imported_text_counted": True}
    assert off["excluded"]["imported_text_counted"] is False


@pytest.mark.unit
@pytest.mark.subsys_lint
def test_mcp_view_says_imported_text_counts() -> None:
    on = {"excluded": {"dirs": ["ext"], "files": [], "imported_text_counted": True}, "quality": 7.0}
    off = {"excluded": {"dirs": ["ext"], "files": []}, "quality": 7.0}
    assert any(CLAUSE in line for line in mcp_view._excluded_lines(on))
    assert not any(CLAUSE in line for line in mcp_view._excluded_lines(off))


@pytest.mark.unit
@pytest.mark.subsys_lint
def test_feature_detection_ignores_a_flag_excluded_skills_folder(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("# P\n\nAlways test.\n", encoding="utf-8")
    skill = tmp_path / ".claude" / "skills" / "s"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: s\ndescription: d\n---\n\nDo it.\n", encoding="utf-8")
    assert detect_features_filesystem(tmp_path).has_skills_dir
    left_out = load_run_exclusions(tmp_path, ["skills"], None)
    assert not detect_features_filesystem(tmp_path, exclusions=left_out).has_skills_dir
