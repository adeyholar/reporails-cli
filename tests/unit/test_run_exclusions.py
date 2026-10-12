"""The run's exclusion set: flag and config union, what it leaves out, what it records, and the link walk."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from reporails_cli.core.classify import classify_files, load_file_types
from reporails_cli.core.classify.link_walker import walk_markdown_links
from reporails_cli.core.discovery.agents import clear_agent_cache
from reporails_cli.core.discovery.exclusions import DEFAULT_EXCLUDE_DIRS, RunExclusions, load_run_exclusions
from reporails_cli.interfaces.cli import check_flow
from reporails_cli.interfaces.cli.check_flow import CheckInputs, CheckState
from reporails_cli.interfaces.mcp import tools


def _write_config(project: Path, body: str) -> None:
    (project / ".ails").mkdir(exist_ok=True)
    (project / ".ails" / "config.yml").write_text(body, encoding="utf-8")


def _gs_project(tmp_path: Path, config: str = "") -> Path:
    project = tmp_path / "proj"
    (project / "ext").mkdir(parents=True)
    (project / "docs").mkdir()
    (project / "CLAUDE.md").write_text(
        "# Proj\n\nAlways run the tests.\n\n@ext/notes.md\n\nSee [ref](ext/ref.md) and [b](docs/b.md).\n",
        encoding="utf-8",
    )
    (project / "ext" / "notes.md").write_text("Always use tabs.\n\n[a](a.md)\n", encoding="utf-8")
    (project / "ext" / "ref.md").write_text("Never skip tests.\n", encoding="utf-8")
    (project / "ext" / "a.md").write_text("See [b](../docs/b.md).\n", encoding="utf-8")
    (project / "docs" / "b.md").write_text("Always lint.\n", encoding="utf-8")
    _write_config(project, "generic_scanning: true\n" + config)
    return project


# ─── The owner ──────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.subsys_map
def test_flags_join_config_for_folders_and_globs(tmp_path: Path) -> None:
    _write_config(tmp_path, "exclude_dirs: [ext]\nexclude_files: ['a/*.md']\n")
    excl = load_run_exclusions(tmp_path, ["docs"], ["b/*.md"])
    assert excl.dirs == {"ext", "docs"}
    assert set(excl.files) == {"a/*.md", "b/*.md"}
    assert excl.walk_dirs == DEFAULT_EXCLUDE_DIRS | {"ext", "docs"}


@pytest.mark.unit
@pytest.mark.subsys_map
def test_leaves_out_tests_user_patterns_only(tmp_path: Path) -> None:
    excl = load_run_exclusions(tmp_path, ["ext"], ["notes/*.md"])
    assert excl.leaves_out(tmp_path / "ext" / "x.md")
    assert excl.leaves_out(tmp_path / "deep" / "ext" / "x.md")
    assert excl.leaves_out(tmp_path / "notes" / "x.md")
    assert not excl.leaves_out(tmp_path / "docs" / "x.md")
    # A built-in default is walked past, never "left out" by the user.
    assert not excl.leaves_out(tmp_path / "vendor" / "x.md")
    assert not RunExclusions.none(tmp_path).leaves_out(tmp_path / "ext" / "x.md")


@pytest.mark.unit
@pytest.mark.subsys_map
def test_leaves_out_logical_resolved_and_symlinked_root(tmp_path: Path) -> None:
    real = tmp_path / "real"
    (real / "ext").mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    # Root given through the link, path given resolved.
    assert RunExclusions(root=link, dirs=frozenset({"ext"})).leaves_out((real / "ext" / "x.md").resolve())
    # Root resolved, path given through the link.
    assert RunExclusions(root=real.resolve(), dirs=frozenset({"ext"})).leaves_out(link / "ext" / "x.md")
    # Glob form through the link.
    assert RunExclusions(root=link, files=("ext/*.md",)).leaves_out((real / "ext" / "x.md").resolve())
    # Relative logical path against an absolute root's cwd-independent form.
    assert RunExclusions(root=real, dirs=frozenset({"ext"})).leaves_out(Path(os.path.relpath(real / "ext" / "x.md")))


@pytest.mark.unit
@pytest.mark.subsys_map
def test_record_sorted_drops_put_back_keeps_unmatched(tmp_path: Path) -> None:
    excl = RunExclusions(root=tmp_path, dirs=frozenset({"zeta", "ext", "gone"}), files=("b/*.md", "a/*.md", "b/*.md"))
    assert excl.record() == (("ext", "gone", "zeta"), ("a/*.md", "b/*.md"))
    put_back = [tmp_path / "ext" / "x.md", tmp_path / "a" / "y.md"]
    assert excl.record(put_back) == (("gone", "zeta"), ("b/*.md",))


# ─── The link walk ──────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.subsys_classify
@pytest.mark.parametrize(
    "excl",
    [
        lambda root: RunExclusions(root=root, dirs=frozenset({"ext"})),
        lambda root: RunExclusions(root=root, files=("ext/*.md",)),
    ],
    ids=["folder", "glob"],
)
def test_walker_never_enters_a_left_out_target(tmp_path: Path, excl) -> None:
    project = _gs_project(tmp_path)
    file_types = load_file_types("claude", project_root=project)
    classified = classify_files(
        project, [project / "CLAUDE.md"], file_types, generic_scanning=True, exclusions=excl(project)
    )
    reached = {cf.path.resolve() for cf in classified}
    assert (project / "docs" / "b.md").resolve() in reached
    assert not any("ext" in p.relative_to(project.resolve()).parts for p in reached)
    # ext/a.md -> docs/b.md is reachable only through a left-out file.
    only = walk_markdown_links(
        {project / "CLAUDE.md": "main"}, project, {project / "CLAUDE.md"}, exclusions=excl(project)
    )
    assert {e.source.name for e in only} == {"CLAUDE.md"}


@pytest.mark.unit
@pytest.mark.subsys_classify
def test_walker_never_skips_a_seed(tmp_path: Path) -> None:
    project = _gs_project(tmp_path)
    seed = project / "ext" / "notes.md"
    edges = walk_markdown_links(
        {seed: "main"}, project, {seed}, exclusions=RunExclusions(root=project, dirs=frozenset({"ext"}))
    )
    assert edges == []  # the seed itself is walked; its only link (a.md) is left out
    other = project / "CLAUDE.md"
    edges = walk_markdown_links(
        {other: "main", seed: "main"}, project, {other, seed}, exclusions=RunExclusions.none(project)
    )
    assert edges


# ─── The scope fold, CLI and MCP ────────────────────────────────────────

_CASES = [
    ("flag-folder", "", ["ext"], None),
    ("config-folder", "exclude_dirs: [ext]\n", None, None),
    ("flag-glob", "", None, ["ext/*.md"]),
    ("config-glob", "exclude_files: ['ext/*.md']\n", None, None),
]


def _fold_names(files) -> set[str]:
    return {Path(f).name for f in files}


@pytest.mark.unit
@pytest.mark.subsys_lint
@pytest.mark.parametrize(("case", "config", "flag_dirs", "flag_files"), _CASES, ids=[c[0] for c in _CASES])
def test_cli_scope_fold_never_checks_a_left_out_file(tmp_path, case, config, flag_dirs, flag_files) -> None:
    project = _gs_project(tmp_path, config)
    clear_agent_cache()
    inputs = CheckInputs(
        targets=[],
        format_opt="json",
        agent="claude",
        exclude_dirs=flag_dirs,
        exclude_files=flag_files,
        ascii_mode=True,
        strict=False,
        verbose=False,
        heal=False,
        dry_run=False,
        cwd=False,
        project_root=project,
    )
    state = CheckState(inputs=inputs)
    state.targets.target = project
    check_flow._resolve_scope_at_target(state)
    check_flow._apply_generic_scan(state)
    names = _fold_names(state.scope.instruction_files)
    assert "CLAUDE.md" in names
    assert not names & {"notes.md", "ref.md", "a.md"}
    assert "docs/b.md" in state.scope.file_type_by_path
    assert not any("ext" in k.split("/") for k in state.scope.file_type_by_path)


@pytest.mark.unit
@pytest.mark.subsys_lint
@pytest.mark.parametrize(("case", "config"), [(c[0], c[1]) for c in _CASES if c[1]], ids=[c[0] for c in _CASES if c[1]])
def test_mcp_discover_files_fold_never_checks_a_left_out_file(tmp_path, case, config) -> None:
    project = _gs_project(tmp_path, config)
    clear_agent_cache()
    discovered = tools._discover_files(project)
    assert isinstance(discovered, tuple)
    names = _fold_names(discovered[2])
    assert "CLAUDE.md" in names
    assert not names & {"notes.md", "ref.md", "a.md"}
    assert "docs/b.md" in discovered[3]
    assert not any("ext" in k.split("/") for k in discovered[3])
    assert discovered[5].dirs | set(discovered[5].files)
