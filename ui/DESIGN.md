# Louvre's web UI: design

The visual and interaction rules for Louvre's pages. Normative: where a page and this file disagree, this file wins
until it is changed in the same PR. The direction is **Annotated**, picked by the operator on 2026-10-23 from the
design study in `docs/ui-explorations/` ([the blend](../docs/ui-explorations/2026-10-23-blends/annotated.html)), which
stays as the record of how it was chosen and is served at `/directions`.

## Direction

A gallery at night. The artifact is the exhibit, hung on a warm wall in a frame of its own; Louvre's chrome is the
label beside it, quiet and small. The conversation is marginalia: notes set in the margin level with the passage they
speak to, numbered like sidenotes, with no boxes around them. Serif for what people read, a small sans for what Louvre
says about it. One accent, oxblood, marks what is live, selected, or the action to take; nothing else is colored for
decoration. Dark is the theme the operator lives in (REQUIREMENTS U2); light is its equal, from the same tokens.

An artifact keeps its author's look. Louvre styles its own chrome and the margin, never what is inside the frame.

## Tokens

Every color is a token, defined for both themes under the same name. Pages use tokens and nothing else: no raw colors,
and a theme difference is a token change, never a rule written for one theme.

| Token | Dark | Light | Role |
|---|---|---|---|
| `wall` | `#13110e` | `#f3eee4` | The page canvas, and the margin. |
| `paper` | `#1c1915` | `#fffdf8` | The frame an artifact hangs in, and an open thread's ground on a phone. |
| `ink` | `#ece5d8` | `#1f1b16` | Primary text. |
| `muted` | `#a69c8c` | `#6d6458` | Labels, metadata, an agent's mark, resolved notes. |
| `faint` | `#6f675b` | `#a8a091` | Rules and decoration only: an anchor's resting underline, a composer's line. Never text. |
| `rule` | `#322c24` | `#e0d6c4` | Every hairline. |
| `accent` | `#d9776c` | `#8a2f2a` | Thread numbers, the active thread's rule, links, the primary action. |
| `accent-ink` | `#13110e` | `#fffdf8` | Text on the accent. |
| `hl` | accent at 16% | accent at 13% | An anchored passage at rest, as a low underline band. |
| `hl-strong` | accent at 30% | accent at 24% | An anchored passage hovered or active, as a full band. |
| `shadow` | black at 60% | ink at 28% | The frame's and an active thread's shadow. |

Text reads at 4.5:1 or better (WCAG AA) on `wall` and `paper` in both themes: `ink` 14 to 17, `muted` 5.0 to 7.0,
`accent` 5.7 to 8.2. `faint` does not (2.2 to 3.4), which is why it is never text; the mock-up uses it for three small
labels, which M2 sets in `muted`.

## Type

| Role | Face | Size and leading | Notes |
|---|---|---|---|
| Artifact title in mock data, page titles | Fraunces 600 | 40/1.12, 28/1.15 on a phone | Tracking -0.01em. |
| Section heads | Fraunces 600 | 23, 21 on a phone | |
| Reading text | Source Serif 4 | 19/1.62, 17/1.58 on a phone | A measure of 60 to 75 characters; 40 to 45 on a phone. |
| Marginalia | Source Serif 4 | 15/1.45 | Names in small caps; an agent's mark in italics. |
| Louvre's labels and controls | Instrument Sans | 11 to 13 | Labels uppercase, tracked 0.1em; the wordmark tracked 0.4em. |

Numbers in tables are tabular. A number keeps its unit on its line (`1.2&nbsp;s`).

## Layout

- **Wide (above 960 px):** the frame and the margin side by side, at most 1180 px together: the frame flexes, the
  margin is 300 px, 40 px between them. The reading measure inside the frame is at most 680 px.
- **Narrow (960 px and below):** the margin becomes a bottom sheet that rises with the open thread, at most 62% of the
  screen. The frame stays.
- **Phone (600 px and below):** the frame goes; the page fills the screen under one hairline. The header is one line
  (wordmark, ticket) and the toolbar one row, with short labels. 20 px side padding.
- Nothing scrolls sideways at any size. Every page is held to the screen matrix (REQUIREMENTS U4), and its
  screenshots are checked in.

## Threads

- **Anchors.** An anchored passage shows a low `hl` band; hovered or active, a full `hl-strong` band. A resolved
  passage shows none until its thread is hovered. The passage's thread number follows its last word, in `accent`,
  superscript.
- **Placement.** A thread sits in the margin level with its passage. When two would overlap, the active thread keeps
  its place and the others move aside, up or down; they animate 200 ms, and not at all under reduced motion.
- **A note.** No box. The author's name in small caps, then the text, inline. An agent's comment adds "(Agent, for
  *person*)" in `muted` italics: it is never mistaken for a person's. The active thread gets an `accent` rule on its
  left; a hovered one too, and its passage lights.
- **Actions** are text links in Instrument Sans: Reply (the primary, in `accent`), Cancel, Resolve. The reply field is
  a single line that grows, with a `faint` underline that turns `accent` on focus. Ctrl or Cmd Enter sends.
- **Resolving** takes a thread out of the margin, with Undo in a toast for five seconds; "All" brings resolved threads
  back, in `muted`.
- **Gone passages.** A thread whose words are not in this version waits below the others, under "Not in this version",
  with its quote struck through and the version it was on. It never moves to other words.
- **Starting one.** Selecting words shows "comment" in the margin level with them (above them on a phone); it, or the
  `c` key, opens a new thread there.
- **Keyboard.** `j` and `k` move between threads in page order, Escape closes one, `c` comments on a selection.

## Chrome

- The header names Louvre and where the artifact came from (its namespace and origin, such as a ticket). Versions are
  a row of small pills in roman numerals; the current one is outlined. The filter is Open (with its count) and All.
- A notice in `accent` names threads whose passages left this version, and jumps to them.
- The frame carries a label row above the artifact (its kind, its age) on wider screens only.

## Not decided yet

- Whether a tablet in portrait (820 px) keeps the margin, narrowed, rather than the bottom sheet.
- The pages M2 adds beyond the artifact's (the list of artifacts) and M3's boards: designed in this direction when
  they are built, and added here.
- Louvre's style for agents (REQUIREMENTS U6) is derived from this file's tokens and type in M2.
