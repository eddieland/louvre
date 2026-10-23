# Decisions

The few choices every developer and agent working on louvre must know, whatever part of the code they work on. It is
kept short so that reading all of it is cheap; every entry added makes that a little less true.

## What belongs here

Most choices do not. An entry earns its place only if an agent working on an unrelated part of louvre could break it,
or reopen it, without knowing. In practice that is one of:

- a constraint or principle that spans the codebase;
- a toolchain choice, or a dependency that code across louvre is shaped around, that handles untrusted input, or that
  would otherwise be proposed again;
- a direction the operator settled that would otherwise be proposed again.

Everything else goes where the next person to change that code will look: why a line of code is the way it is in a
comment at that line, and the story of a change in its PR. A new feature, command, config key, default, or mechanism
is not a decision by itself. When in doubt, leave it out.

## Format

An entry is a title that states the decision and two to four bullets:

- what we chose, if the title does not already say it;
- `Why:` only when it is not obvious;
- `Rejected:` alternatives worth not reconsidering, one line;
- `Revisit:` what would reopen it, one line.

No history of how we got here and no list of what the change touched. A changed choice edits its entry in place, so
the log reads as what is true now; the old text is in git history. Numbers are never reused.

## D001. `pyrefly` strict is the only type checker

- Over `src` and `tests`.
- Rejected: also running `ty` (two checkers to satisfy for little extra coverage).
- Revisit: if strict costs more than it catches; then relax error kinds, not the project.

## D002. ruff selects every stable rule, and preview rules named one by one, the docstring sections' among them

- `select = ["ALL"]`. Opt out with a commented `ignore` or a `noqa` with a code, never by narrowing.
- Preview rules stay off but for those named one by one under `explicit-preview-rules`, so a ruff bump adds none:
  the pydoclint `DOC` rules (a public function's Returns, Yields, and Raises sections must match its body), and
  others chosen for what they catch. Add one by naming it.
- Preview mode also turns on preview behavior in stable rules, so a ruff bump can change the lint; fix or opt out then.

## D003. click for every command line

- louvre's CLI and any program it ships. Only `louvre.cli` imports click; `tests/louvre/test_layers.py` holds it.
- Rejected: argparse; ruff's banned-api rule fails the lint on an import of it.

## D004. The version comes from the latest `v*` tag (uv-dynamic-versioning)

- Pushing the tag is the whole release step, so tag and version cannot disagree. Build-time dependency only.
- Rejected: a static version checked against the tag; hatch-vcs (pulls in setuptools).
- Revisit: if a build that matters runs without tags (shallow clone).

## D005. Every test directory is a package

- Without the root `tests/__init__.py`, pytest names `tests/louvre/` `louvre` and shadows `src/louvre`.
- Rejected: `--import-mode=importlib` (changes how `conftest.py` imports, for no gain).

## D006. pydantic for config and other programs' output; rich for terminal output

- Anything louvre parses from a file or another program is validated by a pydantic model, not by hand.
- Rejected: curses (loses scrollback); hand-written ANSI.

## D007. Postgres holds Louvre's data

- Settled by the operator (2026-10-23): a hosted service for many people, so a managed database, not a file on one
  host. The feed's `seq` and every query rely on it; tests run against a real Postgres, in CI too.
- Rejected: SQLite on one host (ties Louvre to one machine's disk); both behind an interface (two backends to hold to
  one contract).

## D008. An artifact's page is served sandboxed, with only the bridge added

- `/content/...` answers with a `sandbox` Content-Security-Policy and is framed without `allow-same-origin`, so its
  scripts run on an opaque origin and never see a session. Louvre adds one script, the bridge (`ui/src/bridge`), and
  trusts nothing it says further than where a passage is or what was selected.
- Anchors are read the same way on both sides: `louvre.core.text` and `ui/src/bridge/text.ts` answer
  `tests/fixtures/anchors.json` alike; a change to one changes the other.
- Rejected: a second origin for content (a domain to run); marks as `<mark>` elements in the artifact's markup (the
  bridge paints with the CSS Highlight API, so the author's DOM is untouched).

## D009. A write through the web needs `X-Louvre: 1`, and agents write only through `/mcp` with a token

- A form or a link on another site cannot send the header, and a script cannot without a preflight Louvre never
  grants; with `SameSite=Lax` session cookies, that is Louvre's CSRF defense. A new write route goes under `/api` or
  `/auth`, where the middleware holds it.
- `/mcp` takes a bearer token and never a cookie: a person's session cannot be used as an agent's.

## D010. The MCP server is hand-rolled JSON-RPC, as canopy's local store's is

- The tools' definitions and the answering are canopy's (`packages/canopy-artifacts`), ported, so both stores serve
  one contract; Louvre carries it over streamable HTTP, one message a request, answered as JSON.
- Rejected: the `mcp` SDK (its own async stack and transports, for five methods).
- Revisit: if a client needs server-sent events or sessions.
