"""The exclusion set of one run: the folders and file globs the user left out, and the built-in defaults."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reporails_cli.core.discovery.walk import safe_resolve
from reporails_cli.core.platform.config.config import get_project_config
from reporails_cli.core.platform.policy.exclusion import excluded_by_name
from reporails_cli.core.platform.utils.utils import matches_any_glob

DEFAULT_EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        # VCS
        ".git",
        ".svn",
        ".hg",
        # Python
        "__pycache__",
        ".venv",
        "venv",
        ".env",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        # JS/TS
        "node_modules",
        # Build output
        "dist",
        "build",
        "target",
        "out",
        # Data / artifacts (instruction files never live here)
        "data",
        "datasets",
        # Vendored
        "vendor",
        # IDE / OS
        ".idea",
        # `.vscode` is deliberately absent: Copilot declares real config/mcp
        # surfaces there (`.vscode/{settings,mcp}.json`), pre-filtered out otherwise.
    }
)


@dataclass(frozen=True)
class RunExclusions:
    """What a run leaves out.

    `dirs` and `files` are the user's folders and file globs (command line plus config).
    `walk_dirs` adds the built-in defaults and is what directory walks prune.
    """

    root: Path
    dirs: frozenset[str] = frozenset()
    files: tuple[str, ...] = ()
    walk_dirs: frozenset[str] = DEFAULT_EXCLUDE_DIRS

    @classmethod
    def none(cls, root: Path) -> RunExclusions:
        """No user exclusions; walks still prune the built-in defaults."""
        return cls(root=root)

    def leaves_out(self, path: Path) -> bool:
        """True when `path` sits in a folder the user left out or matches a file glob the user left out.

        Built-in defaults never count. The path is tried as given and resolved, against the root as
        given and resolved.
        """
        if not self.dirs and not self.files:
            return False
        roots = (self.root, safe_resolve(self.root))
        for candidate in (path, safe_resolve(path)):
            for root in roots:
                try:
                    parts = candidate.relative_to(root).parts
                except ValueError:
                    parts = ()
                if self.dirs and excluded_by_name(parts, self.dirs):
                    return True
                if self.files and matches_any_glob(candidate, list(self.files), root):
                    return True
        return False

    def record(self, put_back: tuple[Path, ...] | list[Path] = ()) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """The `(folders, file globs)` to report: every user pattern, sorted, without repeats.

        A pattern that a put-back file matches is dropped; a pattern that matches nothing stays.
        """
        dirs = sorted(d for d in self.dirs if not any(self._dir_matches(p, d) for p in put_back))
        files = sorted({g for g in self.files if not any(self._glob_matches(p, g) for p in put_back)})
        return tuple(dirs), tuple(files)

    def _dir_matches(self, path: Path, name: str) -> bool:
        return RunExclusions(self.root, frozenset({name})).leaves_out(path)

    def _glob_matches(self, path: Path, glob: str) -> bool:
        return RunExclusions(self.root, files=(glob,)).leaves_out(path)


def load_run_exclusions(
    target: Path, flag_dirs: list[str] | None = None, flag_files: list[str] | None = None
) -> RunExclusions:
    """The run's exclusions at `target`: command-line patterns joined with the project's config."""
    config = get_project_config(target)
    dirs = frozenset((*(flag_dirs or ()), *config.exclude_dirs))
    files = tuple(dict.fromkeys((*(flag_files or ()), *config.exclude_files)))
    return RunExclusions(root=target, dirs=dirs, files=files, walk_dirs=DEFAULT_EXCLUDE_DIRS | dirs)
