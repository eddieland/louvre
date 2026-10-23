# ui/AGENTS.md

Rules for any agent working in `ui/`, Louvre's web UI. The repository's `AGENTS.md` still applies; this adds what is
specific here. Read `DESIGN.md` in this directory before changing anything visible: it is normative.

## Stack

Pinned exactly in `package.json`, as canopy's UI pins the same packages. Check the current docs for these versions
before using an API; do not code from memory, and do not upgrade in passing.

- Vite 8 single-page app, served by FastAPI at the root (`louvre.web.app`). No server rendering. The bridge,
  `src/bridge/`, is built apart into `dist/bridge/bridge.js` (`vite.bridge.config.ts`), and the server adds it to every
  artifact's page.
- React 19.3 with the React Compiler (`@vitejs/plugin-react` `compiler: true`).
- TypeScript strict, with `noUncheckedIndexedAccess`.
- Tailwind v4, configured in CSS (`src/index.css`, `src/styles/tokens.css`). There is no `tailwind.config.js`.
- TanStack Router (file-based, `src/routes/`) and TanStack Query.
- Fraunces, Source Serif 4, and Instrument Sans, self-hosted from Fontsource: the page loads nothing from another
  origin.
- oxlint (with the React Compiler's rules, eslint-plugin-jsdoc's, and type-aware rules through oxlint-tsgolint),
  oxfmt, and Vitest.

Add a library as the repository's `AGENTS.md` says, when it clearly beats the code we would write instead, and pin it
exactly like the rest.

## Commands

From `ui/`, or `make ui-check`, `make ui-build`, `make ui-fmt` from the root:

| Command | Does |
|---|---|
| `npm run dev` | Vite on 127.0.0.1:5173, proxying `/api`, `/auth`, `/content`, and `/mcp` to `npm run dev:api` |
| `npm run check` | format check, lint, typecheck, unit tests, build: what CI runs |
| `npm test -- <files>` | the Vitest files named |
| `npm run fmt` | format with oxfmt |

`make screens` and `make screenshots` build `ui/` first: its pages are in the screen matrix like every other page.

## Rules

- **The lint is strict.** oxlint runs every rule in its correctness, suspicious, pedantic, and perf categories, and
  the style and restriction rules `.oxlintrc.json` names one by one; a rule turned off there says why. It runs with
  `--type-aware`. Fix what it finds. A line that must break a rule carries `oxlint-disable-next-line` with the rule's
  name and a comment saying why.
- **Tokens only.** No raw colors and no `dark:` in components; a theme difference is a token change in
  `src/styles/tokens.css`. `scripts/check-source.mjs`, part of `npm run lint`, fails otherwise.
  `src/styles/tokens.test.ts` holds every text token to WCAG AA on every base, in both themes.
- **Type and layout come from `src/index.css`'s utilities** (`title`, `heading`, `reading`, `stage`, `sheet`, `note`),
  which say in CSS what `DESIGN.md` says in prose. A new recurring style becomes a utility there, not arbitrary values
  repeated across components.
- **Every export has a JSDoc comment**, and so does each field of an exported interface: what it is or does, in
  prose. No types in it: TypeScript has them. The lint enforces both.
- **No hand-written memoization.** The compiler memoizes. `useMemo`, `useCallback`, and `memo` are banned by the lint.
- **An artifact is untrusted.** Its HTML is only ever shown in an `<iframe sandbox>` without `allow-same-origin`, from
  the server's sandboxed route (REQUIREMENTS L7). Never render it, or a comment's text, as HTML in Louvre's own page:
  `react/no-danger` is on.
