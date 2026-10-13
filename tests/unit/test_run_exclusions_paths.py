"""Folder values with slashes, and the paths imported text is read from."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from reporails_cli.core.discovery import exclusions as exclusions_module
from reporails_cli.core.discovery.exclusions import FolderValueError, RunExclusions, load_run_exclusions
from reporails_cli.core.pipeline.assemble import AssembleInputs, _imported_note, _imports_left_out


@pytest.mark.unit
@pytest.mark.subsys_lint
def test_trailing_slash_and_dot_prefix_normalize(tmp_path: Path) -> None:
    left_out = load_run_exclusions(tmp_path, ["rules/", "./docs/", "/", ""], None)
    assert left_out.dirs == frozenset({"rules", "./docs"})
    assert left_out.record() == (("./docs", "rules"), ())
    assert "rules" in left_out.walk_dirs
    assert left_out.leaves_out(tmp_path / "x" / "rules" / "a.md")
    assert left_out.leaves_out(tmp_path / "docs" / "a.md")


@pytest.mark.unit
@pytest.mark.subsys_lint
def test_path_form_value_is_relative_to_the_root(tmp_path: Path) -> None:
    path_form = load_run_exclusions(tmp_path, [".claude/rules"], None)
    assert path_form.leaves_out(tmp_path / ".claude" / "rules" / "a.md")
    assert not path_form.leaves_out(tmp_path / "docs" / "rules" / "b.md")
    assert not path_form.leaves_out(tmp_path / "x" / ".claude" / "rules" / "a.md")
    assert ".claude/rules" not in path_form.walk_dirs
    assert ".claude/rules" not in path_form.feature_walk_dirs
    name_form = load_run_exclusions(tmp_path, ["rules"], None)
    assert name_form.leaves_out(tmp_path / ".claude" / "rules" / "a.md")
    assert name_form.leaves_out(tmp_path / "docs" / "rules" / "b.md")
    assert "rules" in name_form.walk_dirs


@pytest.mark.unit
@pytest.mark.subsys_lint
def test_root_is_resolved_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    left_out = load_run_exclusions(tmp_path, ["ext"], None)
    calls: list[Path] = []
    real = exclusions_module.safe_resolve

    def spy(p: Path) -> Path:
        calls.append(p)
        return real(p)

    monkeypatch.setattr(exclusions_module, "safe_resolve", spy)
    for i in range(5):
        left_out.leaves_out(tmp_path / f"d{i}" / "a.md")
    assert calls.count(tmp_path) == 1


_TREE = ("docs/a.md", "pkg/docs/b.md")


def _tree(root: Path) -> tuple[Path, Path]:
    for rel in _TREE:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("# x\n", encoding="utf-8")
    return root / _TREE[0], root / _TREE[1]


@pytest.mark.unit
@pytest.mark.subsys_lint
@pytest.mark.parametrize(
    ("value", "left_out_files", "recorded"),
    [
        ("docs", (True, True), "docs"),
        ("docs/", (True, True), "docs"),
        ("./docs", (True, False), "./docs"),
        ("/docs", (True, False), "./docs"),
        ("./docs/", (True, False), "./docs"),
        ("pkg/docs", (False, True), "pkg/docs"),
        ("./pkg/docs/", (False, True), "pkg/docs"),
        ("/pkg/docs", (False, True), "pkg/docs"),
    ],
)
def test_folder_value_forms(tmp_path: Path, value: str, left_out_files: tuple[bool, bool], recorded: str) -> None:
    root_docs, pkg_docs = _tree(tmp_path)
    left_out = load_run_exclusions(tmp_path, [value], None)
    assert (left_out.leaves_out(root_docs), left_out.leaves_out(pkg_docs)) == left_out_files
    assert left_out.record() == ((recorded,), ())
    # Whatever the Excluded line lists leaves something out.
    assert left_out.leaves_out(root_docs) or left_out.leaves_out(pkg_docs)


@pytest.mark.unit
@pytest.mark.subsys_lint
@pytest.mark.parametrize("value", ["docs/*", "**/docs", "[ab]", "a/../b", "docs\\x", "d?cs", ".."])
def test_refused_folder_values(tmp_path: Path, value: str) -> None:
    with pytest.raises(FolderValueError, match="not a folder name or a folder path"):
        load_run_exclusions(tmp_path, [value], None)
    (tmp_path / ".ails").mkdir()
    (tmp_path / ".ails" / "config.yml").write_text(f"exclude_dirs: [{value!r}]\n", encoding="utf-8")
    with pytest.raises(FolderValueError, match="exclude_dirs in the config"):
        load_run_exclusions(tmp_path, None, None)


@pytest.mark.unit
@pytest.mark.subsys_lint
def test_exclusion_sets_are_built_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root_docs, pkg_docs = _tree(tmp_path)
    left_out = load_run_exclusions(tmp_path, ["pkg/docs", "x"], ["*.tmp"])
    built: list[object] = []
    real = exclusions_module._split_dirs
    monkeypatch.setattr(exclusions_module, "_split_dirs", lambda d: built.append(d) or real(d))
    for _ in range(4):
        assert left_out.leaves_out(pkg_docs)
        assert not left_out.leaves_out(root_docs)
    assert len(built) == 1


@pytest.mark.unit
@pytest.mark.subsys_lint
@pytest.mark.parametrize("where", ["flag", "config"])
def test_check_refuses_a_bad_folder_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, where: str) -> None:
    from typer.testing import CliRunner

    from reporails_cli.interfaces.cli.main import app

    _tree(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("# P\n", encoding="utf-8")
    (tmp_path / ".ails").mkdir()
    flags: list[str] = []
    if where == "flag":
        (tmp_path / ".ails" / "config.yml").write_text("default_agent: claude\n", encoding="utf-8")
        flags = ["--exclude-dirs", "**/docs"]
    else:
        (tmp_path / ".ails" / "config.yml").write_text("exclude_dirs: ['docs/*']\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AILS_DEV_MODE", "1")
    result = CliRunner().invoke(app, ["check", *flags])
    assert result.exit_code == 2
    assert "Error:" in result.output
    assert "not a folder name or a folder path" in result.output
    assert "--exclude-files takes file patterns" in result.output
    assert "Traceback" not in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)


def _atom(file_path: Path, imported_from: str) -> SimpleNamespace:
    return SimpleNamespace(
        file_path=str(file_path), imported_from=imported_from, imported_line=3, text="Keep it small."
    )


@pytest.mark.unit
@pytest.mark.subsys_lint
def test_symlinked_importer_reads_the_source_next_to_the_real_file(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    (root / "shared").mkdir()
    (root / "shared" / "CLAUDE.md").write_text("# P\n", encoding="utf-8")
    (root / "CLAUDE.md").symlink_to(root / "shared" / "CLAUDE.md")
    atom = _atom(root / "CLAUDE.md", "../ext/notes.md")
    inp = AssembleInputs(
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
    assert _imports_left_out(inp, RunExclusions(root, dirs=frozenset({"ext"})))
    assert "(from ext/notes.md:3" in _imported_note(atom, root)
