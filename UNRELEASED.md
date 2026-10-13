# Unreleased

### Added

- Check: announcements from reporails can show as a short highlighted block under the header, once a day. `ails check --no-promo` or `AILS_NO_PROMO=1` hides them, and messages about your account still show. In `ails check -f json` and the MCP `validate` reply each notice carries `kind` (`notice` or `promo`), `--format github` leaves announcements out of its annotations, and the MCP text view marks them `promo`.
- Check: `ails check -f json` and the MCP `validate` reply carry `not_evaluated`, the `{rule, file}` pairs of checks that did not finish on a file (`[]` when every check finished). Text output names them in one line per file under the results.

### Changed

- Check: file patterns you leave out with `--exclude-files` now add to the `exclude_files:` patterns in your config instead of replacing them, the same way `--exclude-dirs` adds to `exclude_dirs:`.
- Check: a file or capability you name on the command line (`ails check docs/a.md`, `ails check skills:backlog`) or validate on its own through MCP (only that file, not other targets in the same call) is checked even inside a folder you left out and counts toward your level; it is no longer listed on the `Excluded` line, and text a checked file imports from it is not reported as imported from a left-out file.
- Check: with `generic_scanning: true`, a file or folder you leave out is no longer checked through an `@` import or a link.
- Check: text a checked file imports with `@path` from a file you left out still counts inside the importing file, and the `Excluded` line ends with `; imported text in checked files still counts`. `ails check -f json` and the MCP `validate` reply carry `imported_text_counted` under `excluded`; it is `false` when no import crosses into a left-out file.
- Check: a capability you leave out, by folder name (`--exclude-dirs skills`) or by file pattern (`--exclude-files '.claude/skills/**'`), is no longer counted as present, so it no longer raises your level; a file you name on the command line still counts.
- Check: a project over the 10,000-atom cap now gets a route to a score. The message names the densest folders with their atom counts and gives one ready `ails check --exclude-dirs …` command that leaves out enough of them for the rest of the project to be checked and scored, keeping as much checked as it can. It says excluded folders are not checked and that `exclude_dirs:` in `.ails/config.yml` keeps them out on every run. Pro keeps the contact link after the route.
- Check: when you leave folders or files out of a run (`--exclude-dirs`, `--exclude-files`, or `exclude_dirs:` / `exclude_files:` in your config), the summary names them on an `Excluded` line under the score: they are not checked, and the score covers the rest. `ails check -f json` and the MCP `validate` reply carry them as `excluded` (`{dirs, files}`). The folders and files skipped by default (such as `node_modules`) are not listed.
- Settings: `AILS_MODEL_OFFLINE`, `AILS_NO_PROMO` and the other on/off environment variables are on for any value except `0`, `false`, `no` or `off`, so `AILS_MODEL_OFFLINE=off` now leaves the model download on.
- Check: the message for a project too large to score in one request points to leaving folders out with `--exclude-dirs` or `exclude_dirs:` in `.ails/config.yml`, instead of checking a sub-folder on its own, which reads the files differently.
- Rules: CORE:C:0037 (Static Before Dynamic) and CORE:G:0007 (Project Config Self-Contained) finish on large files in a fraction of the time. CORE:C:0037 counts a heading only when a space or tab follows its `#` marks, so a file of bare `#` lines is no longer read as having sections. CORE:G:0007 reads "requires … install" as an external dependency when both words are on one line within 120 characters. Neither rule counts toward a file's score; their findings can change.

### Fixed

- Check: a project whose only agent files are rule files (such as `.claude/rules/*.md` with no `CLAUDE.md`) is still checked and scored when you leave folders or files out of the run, even when nothing matches them, and leaving out a project's main instruction file no longer leaves out its rule files.
- Check: a project with a line that holds a very long run of code or formatting spans, such as a generated docs index, is scored again. Such a line no longer leaves the whole project with no score and an "unrecognized" error.
- Check: a rule check that does not finish in time on a very large file no longer reports a finding it never confirmed, or misses one it never looked for. It reports nothing for that file and is listed as not evaluated.
- Check: when the diagnostics server you set with `AILS_SERVER_URL` is busy or takes too long, `ails check` says so and tells you when to try again, instead of reporting a plain HTTP error. A project too large to score gets its own message there too.

### Removed

### Internal

- Tests: the integration and MCP test doubles accept the exclusions a run passes through.
