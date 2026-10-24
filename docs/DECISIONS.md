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
- The policy lets a page load from the network only what Louvre serves every page alike, at a version, with
  `Access-Control-Allow-Origin: *`, as an opaque origin's loads need: the house style's fonts, at
  `/style/<version>/fonts/` (settled by the operator, 2026-10-24), and the map kit, at `/kit/<version>/`, whose one
  script may run, whose worker runs from a blob, and whose basemap, street tiles, and glyphs it reads
  (`louvre.core.maps`). Beside them, its own version's files (D012). Anything else a page shows it carries inline.
- The street tiles are the one thing Louvre's server fetches from another site for a page: OpenStreetMap's, from
  OpenFreeMap (picked by the operator, 2026-10-24, over hosting tiles ourselves), passed on at the kit's path, so a
  page still reaches nothing but Louvre. `LOUVRE_STREETS` names another source, or none.
- Anchors are read the same way on both sides: `louvre.core.text` and `ui/src/bridge/text.ts` answer
  `tests/fixtures/anchors.json` alike; a change to one changes the other.
- Rejected: a second origin for content (a domain to run); marks as `<mark>` elements in the artifact's markup (the
  bridge paints with the CSS Highlight API, so the author's DOM is untouched).

## D009. A write through the web needs `X-Louvre: 1`, and agents write only through `/mcp` with a token

- A form or a link on another site cannot send the header, and a script cannot without a preflight Louvre never
  grants; with `SameSite=Lax` session cookies, that is Louvre's CSRF defense. A new write route goes under `/api` or
  `/auth`, where the middleware holds it.
- `/mcp` takes a bearer token and never a cookie: a person's session cannot be used as an agent's.

## D010. The MCP server is the MCP SDK's low-level server, serving canopy's tool definitions

- Settled by the operator (2026-10-24). The SDK speaks the protocol and streamable HTTP; louvre.mcp lists canopy's
  definitions (`packages/canopy-artifacts`) as they are, so both stores serve one contract, and answers each call
  from the store. Stateless, answered in JSON, with no stream: any instance answers any request, as on Vercel.
- Tests reach it through the SDK's own client, in process and over HTTP, as agents' runtimes do.
- Rejected: hand-rolled JSON-RPC (every protocol version, and resources and prompts, by hand); the SDK's `MCPServer`
  (schemas from function signatures, not canopy's).

## D011. Louvre's own tools are added beside the contract's, and change none of them

- The contract's eight tools, their results, and `comment_feed`'s kinds are canopy's (REQUIREMENTS L1). A tool of
  Louvre's own (the `style_` and `decision_` tools, and `files_publish`) is a new name; what it records that a reader
  follows gets a feed of its own (`decision_feed`), never a new kind in `comment_feed`, which canopy's loop reads.
- Rejected: decisions' events in `comment_feed` (a reader written against the contract meets kinds it does not know).
- Revisit: when canopy's contract takes a tool of Louvre's, which then follows the contract's word.

## D012. A version's files are served under a key in their path, never behind a session

- A version with files is served at `/content/<artifact>/<n>/<key>/`, its files under it, the key 128 random bits. A
  page runs on an opaque origin (D008), so its requests for its files carry no cookie; the key, which only a person
  who may read the version learns, by being sent to it, is what a request for a file needs.
- The page's policy lets it load files from that path and nowhere else, so it reads its own version's files, never
  another's.
- Rejected: files behind a session (a sandboxed page's requests carry none); a key in the frame's URL that the UI
  asks for (`/content/<artifact>/<n>` answers a signed-in person with a redirect to it, so no frame changes); files
  across an artifact or a namespace (a version would not keep its own).
- Revisit: if a file must be taken back from someone who already has its path.
