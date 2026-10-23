# AGENTS.md

Instructions for any agent working in this repository. Humans should read it too.

## Read this first, in order

1. `README.md`: what we are building and for whom.
2. `docs/REQUIREMENTS.md`: what Louvre must do, from what canopy needs of it, and where it stands on each. canopy's
   artifacts contract, which it cites, is normative.
3. `docs/roadmap/README.md`: milestones in order, each one's status, and a file per milestone with its acceptance
   criteria. Read the file of the milestone your work belongs to.
4. `docs/DECISIONS.md`: the few choices every agent must know, whatever it works on. Read it whole; add to it rarely.

## How to work

- Work one milestone at a time. Do not start milestone N+1 until milestone N meets its acceptance criteria. A change
  the operator asks for directly goes ahead without one. Keep the milestone's `Status:` line current, and its line in
  `docs/roadmap/README.md` with it.
- Small PRs. One concern per PR. Conventional commit messages.
- A PR description fills `.github/pull_request_template.md` briefly: a reviewer takes it in at a glance, and the
  detail stays in the diff. Not a wall of text.
- Add a dependency judiciously: when it clearly beats the code we would write instead, and its PR says why. It gets a
  `docs/DECISIONS.md` entry only when it passes that file's bar. A dev-only tool (a linter, a checker, a test plugin)
  gets a comment where it is configured saying what it is for.
- Most PRs add no decision entry. `docs/DECISIONS.md` holds only what every future agent must know, whatever part of
  the code it works on. The test: could an agent working on an unrelated part of louvre break it, or reopen it, without
  knowing? If not, it is not a decision entry. Why a line of code is so goes in a comment there; the story of a change
  goes in its PR. When in doubt, leave it out.
- When unsure, prefer the smaller change and leave a note in the PR. Do not invent requirements.

## Toolchain

- Python 3.12+. Package layout `src/louvre/`. CLI entry point `louvre`.
- `uv` for everything: `uv sync`, `uv run`, `uv tool install`.
- `ruff` for formatting and linting. `pyrefly` in strict mode for type checking (D001). `pytest` for tests, in strict
  mode, where a warning fails the test that raised it.
- `rumdl` lints and formats Markdown with every default rule. `editorconfig-checker` (`ec`) holds every file that is
  not Python or Markdown to `.editorconfig`. `shellcheck` lints shell scripts, `actionlint` the GitHub workflows, and
  `zizmor` their security: every action is pinned to a commit, and a finding it allows is ignored inline with a reason.
  All are dev dependencies, so `uv sync` installs them and `make lint` runs them.
- ruff selects every stable rule, and preview rules named one by one, the pydoclint ones among them (D002): a public
  module, class, or function has a Google docstring, with Returns, Yields, and Raises sections that match its body.
  Every docstring, a test's included, opens with a one-line summary ending in a period, and a blank line before
  anything more. Opt out with a commented `ignore` entry or a `noqa` with a code; never narrow `select`.
- `make all` runs fmt, lint (including type checks), and tests; `make check` is the same without fmt, and never
  rewrites files. CI runs `make check`, and is the backstop for the whole suite. An agent does not run `make all` or
  `make check` before pushing unless the operator asks. Every formatter and linter is cheap, so it runs them all; the
  tests it runs are the ones its change reaches.
  - Always `make fmt` and `make lint`: every formatter, then every linter and the type checker, over the whole
    repository, in seconds.
  - Optionally `make hooks`, once per clone: prek's git hooks (`prek.toml`) then run the same formatters and linters
    on each commit's files. They do not replace the step above. A Claude Code cloud session installs them when it
    starts (`.claude/settings.json`).
  - Tests: `uv run pytest -q <test modules>` for the package you changed, which sits parallel to it under `tests/`
    (add `-n auto` for a directory). Add the whole-louvre tests your change can trip: `tests/louvre/test_layers.py`
    for a new import or module, `test_frozen.py` for a dataclass.
  - A change to a page the web app serves, or a new page: `make screenshots`, which checks every page at every screen
    size in the matrix (`tests/louvre/web/test_screens.py`, REQUIREMENTS U4) and rewrites `docs/screenshots/` and its
    gallery. Commit them, and look at the diff: they are the record of how each page looks on each screen. A new page
    gets a scene in the matrix in the same PR. `make test` fails on a screenshot missing or a stale gallery.

  CI skips every check on a pull request that changes only docs, so there the checks you run are the only ones.
- A pull request's CI is the run GitHub starts for it. Never start CI by hand on a branch with an open pull request
  (`workflow_dispatch`): the manual run shares the pull request's concurrency group and cancels its run.
- Stdlib first. Add a third-party dependency only when stdlib makes the code materially worse, and say why in its PR.
  Adopted so far: `click` for every command line, never argparse (D003), `pydantic` for validating config and anything
  parsed from another program's output, `rich` for terminal output (D006), `fastapi` and `uvicorn` for the web app
  (only in `louvre.web` and `louvre serve`), `httpx2` for its test client (dev only), `hypothesis` for property tests
  of input validators (dev only), `pytest-xdist` to run the tests in parallel (dev only), and `syrupy` for snapshot
  tests (dev only).

## Formatting

**Maximum line length is 120 characters. For every file type, not just Python.**

- This covers Python, Markdown, TOML, YAML, shell, and anything else in the repo.
- `.editorconfig` is the source of truth for whitespace: `max_line_length = 120`, UTF-8, LF line endings, final
  newline, 4-space indent (2 for TOML, YAML, JSON, SQL; tabs in `Makefile`). Configure your editor to honor it.
- `ruff` enforces 120 for Python (`[tool.ruff] line-length = 120`), `rumdl` for Markdown (`[tool.rumdl] line-length`),
  and `ec` for every other file, from `.editorconfig`. Keep the three in sync.
- Do not introduce any other line-length target (80, 88, 100). Do not reflow existing text just to fill 120 columns;
  wrap new or edited prose at 120.
- The only exceptions are lines that cannot be broken: long URLs, Markdown tables and code blocks, and generated files
  such as `uv.lock`.

## Code conventions

- Fully typed. `pyrefly` strict clean, the tests included.
- A parameter takes the most general type its body needs; a return keeps the concrete type it builds. `Iterable` for one
  pass; `Collection` for `len`, `in`, or more than one pass; `Sequence` for indexing, slicing, `reversed`, or an order
  the output keeps; `Mapping` for a dict only read. A `set` or `frozenset` tested with `in` becomes
  `collections.abc.Set`, imported as `AbstractSet`, not `Collection`: a `Collection[str]` would also take a bare `str`,
  where `in` is a substring test. A parameter stays concrete when the function mutates, stores, or returns it, or hands
  it to `json.dumps` or `isinstance`; a click command's parameters stay the tuple click passes. No linter checks this,
  so review does.
- A frozen dataclass holds no mutable collection type: a field is typed `Sequence`, `Collection`, `Mapping`, or
  `Set` (as `AbstractSet` where imported so) by what its readers need, as a parameter is, so the type checker refuses
  a change through it. A class that keeps state it changes is not frozen. `tests/louvre/test_frozen.py` fails on a
  `list`, `dict`, or `set` field.
- Every command line is click, never argparse (D003); ruff's banned-api rule fails the lint on an argparse import.
- Modules are small and named for what they own. Only `louvre.cli` imports click; `tests/louvre/test_layers.py` fails
  otherwise.
- No global mutable state. Pass what a function needs.
- Every module is in newspaper order, so it reads top-down from what to how: the docstring, then the public names
  other modules use, most important first, then the private helper functions, each below the first function that
  calls it. What Python needs at import time comes first regardless: constants, type aliases, and anything used as a
  base class, decorator, or default value.
- A comment that says what a name is, for a module's constant or type alias, a class attribute, a field of a
  dataclass, pydantic model, or `NamedTuple`, or an enum member, is a Sphinx doc comment: lines starting `#:`
  directly above the name, so editors and doc tools attach it to the name. A note on why the code is so stays a plain
  `#`. A class's docstring says what the class is; what one field holds goes on that field, not in the docstring.
- A closed vocabulary (a status, a kind) is a `StrEnum`. New code writes and compares it through its members, not bare
  strings. A branch over one is a `match` ending in `case _: assert_never(...)`, so a new value fails the type check
  until every branch handles it.
- Log with `logging`, not `print`.

## Testing

- Patch with `unittest.mock`, as context managers, never pytest's `monkeypatch`. Import the namespace,
  `from unittest import mock`, and spell it out: `mock.patch.dict(os.environ, {...})` for environment variables (pop
  a variable inside the block to unset it), `mock.patch.object(module, "NAME", value)` for an attribute, and
  `contextlib.chdir` for the working directory. ruff fails the lint on `pytest.MonkeyPatch` and on
  `from unittest.mock import ...`.
- A mock is specced: `mock.patch.object(module, "fn", autospec=True)`, with `side_effect` or `return_value` for what
  it does, or `mock.create_autospec(...)`, so a call the real thing would refuse fails the test. Never a bare
  `Mock()` or `MagicMock()`; ruff fails the lint on them. Patching a plain value (a limit, a constant) needs no spec.
- A patch lasts as long as its `with` block. A fixture that patches yields inside the block. A helper that sets up
  state for the code after it is a context manager, and a helper that needs a patch only while it runs opens and
  closes its own.
- What two test modules share lives in one place, never in a test module: `tests/conftest.py` for fixtures. A test
  module imports from no other test module.
- Every test directory has an `__init__.py`, `tests/` included (D005). ruff's `INP001` fails the lint on one that does
  not. The root one matters most: without it, `tests/louvre/` is imported as a package named `louvre` and shadows
  `src/louvre`.
- A test module sits parallel to the package it tests: `tests/louvre/cli/` holds the tests of `louvre.cli`. Only tests
  of louvre as a whole (its layers, its frozen dataclasses) sit in `tests/louvre/` itself.
- What louvre renders whole is held by a snapshot test, with syrupy's `snapshot` fixture, recorded in the test's
  `__snapshots__/` directory. `make snapshots` records the ones that differ, and the diff is reviewed with the change.
- A connection, file, or pipe left open raises a ResourceWarning, which fails the test like any other warning.
- A test waits on a condition, never on time: a loop with a deadline that polls for what it needs, never a fixed
  sleep. When a test is suspected of being flaky, run it many times over with `make burn-in`. A PR that fixes a flaky
  test says it passed the burn-in: one green run cannot tell a fix from a failure made rarer.

## Definition of done for a PR

- The checks and tests the change reaches pass (Toolchain), and CI passes.
- New behavior has a test.
- A page the change touches fits every screen in the matrix, and its screenshots are current (`make screenshots`).
- Docs updated: `README.md` if the install path or daily surface changed, and `DECISIONS.md` only if the change passes
  its bar.
