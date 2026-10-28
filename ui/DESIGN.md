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
decoration. The one other hue, a quiet sage, marks words a version changed, and only while versions are compared
(Changes). Dark is the theme the operator lives in (REQUIREMENTS U2); light is its equal, from the same tokens.

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
| `chg` | sage at 20% | green at 16% | Words a later version added or rewrote, at rest, while comparing versions. |
| `chg-strong` | sage at 38% | green at 30% | Those words hovered or active. |

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
- **Narrow (960 px and below), a tablet in portrait too:** the margin becomes a bottom sheet that rises with the open
  thread, at most 62% of the screen. The frame stays.
- **Phone (600 px and below):** the frame goes; the page fills the screen under one hairline. The header is one line
  (wordmark, ticket) and the toolbar one row, with short labels. 20 px side padding.
- Nothing scrolls sideways at any size. Every page is held to the screen matrix (REQUIREMENTS U4), and its
  screenshots are checked in.

## Threads

- **Anchors.** An anchored passage shows an `hl` band; hovered or active, an `hl-strong` band. A resolved passage shows
  none until its thread is hovered, then a `rule` band. The passage's thread number follows its last word, in
  `accent`, superscript. Inside an artifact the bridge paints these with the CSS Custom Highlight API, which colors
  text and changes none of the author's markup; it draws a full band, not the low one Louvre's own pages can.
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
- **On a map.** On GeoJSON Louvre draws, a tap on a feature, or off every feature on a point, is a selection too, and
  shows "comment" level with it. A place's thread is marked on the map by a disc ringed in `accent` with its number,
  filled `accent` while hovered or active, `muted` when resolved, and its note sits level with the disc. Its quote is
  the feature's label or the point's latitude and longitude.
- **A box on a map.** The map's controls end with a box button, a dashed square; pressed, it fills `accent`, and a
  drag, a finger's too, draws a box rather than moving the map, dashed in `accent` over a faint `accent` tint, and
  shows "comment" beside it. Its thread's box is edged in `accent` (`muted` when resolved, dashed while a draft),
  tinted while hovered or active, its disc on its north-west corner. Its quote is its south-west and north-east
  corners', each as a point's. Escape, or a drag too short to be a box, draws none.
- **Where you stand.** On a map Louvre draws, read by touch, "Comment where you are" in the toolbar ("Here" on a
  phone) asks the browser where the reader is, from Louvre's own page and never the artifact's frame, and opens a
  point's thread there, the map shown at it. The reading's accuracy rings the point, a faint `accent` tint edged in
  `accent`, and its quote ends with it: "within 12 m". A reading refused, or that does not come, says so in a toast.
- **Keyboard.** `j` and `k` move between threads in page order, Escape closes one, `c` comments on a selection.

## Chrome

- The header names Louvre and where the artifact came from (its namespace and origin, such as a ticket). Versions are
  a row of small pills in roman numerals; the current one is outlined. The filter is Open (with its count) and All.
- A notice in `accent` names threads whose passages left this version, and jumps to them.
- The frame carries a label row above the artifact (its kind, its age) on wider screens only.
- The header centers the wordmark over the page's provenance on wide screens, with the person's links (the theme,
  Inbox with how many artifacts have news, Decisions with how many wait on them, both counts in `accent`, Tokens,
  signing in or out) at its right, in Instrument Sans. A phone's one line leaves Tokens out: minting one is a desk
  task.
- Threads on the whole artifact sit at the top of the margin; "Comment on the page" in the toolbar starts one.
- An older version says so under the toolbar, in `accent`, with a link to the latest: comments go on the latest only.
- From version II on, "Changes" in the toolbar compares the version shown with the one before it (Changes).
- A deployment's banner, when its owner sets one, sits above the header (The owner's words).

## The owner's words

What an organization that runs Louvre says on its pages (REQUIREMENTS U13, docs/DEPLOY.md): whose deployment it is,
where to ask for help, its conventions. They are the owner's, not Louvre's and not an artifact's, so they keep to
Louvre's quiet voice and never compete with the exhibit. Each shows only when set.

- **The banner** sits above the header on every page, an artifact's and a board's too: one line where it fits, on
  `paper` under a `rule` hairline, in Instrument Sans at 12, `ink`, centered; on a phone, left-aligned at the page's
  20 px padding, and wrapped. It is never `accent`: the accent marks what is live, and the banner is always there.
- **The footer** closes the catalogue's column, on the catalogue, the demo, the inbox, decisions, tokens, and signing
  in: a `rule` hairline, then the owner's lines in Instrument Sans at 12 and `muted`. An artifact's and a board's pages
  have none: their foot is the exhibit's.
- **Notes** sit in the page's own prose, as its own sentences do: the note on signing in above the ways to sign in,
  wherever a person is asked to; the note on tokens under what a token is, in `muted`.
- **The name** is the tab's, after the page's (`Inbox · Acme Louvre`); the wordmark stays Louvre's.
- **Their marks.** Bold, italics, and code as the owner wrote them; links in `accent`, underlined, as Louvre's are. A
  link to another site opens in a tab of its own. Nothing else of Markdown is kept, and nothing is drawn as HTML.

## Changes

What a revision changed, for the reader who commented on the version before it (REQUIREMENTS U8). Comparing is a
state of the artifact's page, linked by `?changes=N`, the earlier version's number: the frame, the toolbar, and the
margin are the page's own, and the artifact keeps its author's look.

- **In the frame**, the bridge paints the words the later version added or rewrote with a `chg` band, `chg-strong`
  hovered or active, as it paints a thread's passage, changing none of the author's markup. Words removed are not on
  the page to paint; their note sits level with where they were.
- **In the margin**, the threads make way. A summary heads it: since which version, how many changes and words, and
  each thread on the earlier version's text by who started it and what they said, then what became of its passage
  (unchanged, changed beside it, or reworded or removed, the last two in `accent`), whether it is resolved, and its
  replies since. Activating one leaves the comparison with that thread open. Below the summary, each change is a note
  level with its passage, like a thread's: its kind as a label (Added, Removed, Rewritten), the words it removed
  struck through, and the words it added on a `chg-strong` underline, four lines of each at most.
- **On a map** Louvre draws, each feature the later version added, removed, or moved is lit on the map in the same
  sage, at full strength: a halo under it where it is now, for one added or moved; where it was, dashed and hollow, for
  one removed or moved; and a dotted line between the two for one moved. Each is a note in the margin level with it,
  its kind as a label ("Moved on the map"), the feature's label on a `chg-strong` underline, struck through when
  removed, and how far and which way it moved in `muted` (`14 m north-west`, or "Reshaped where it was"). Opening a
  note, or tapping the feature, pans and zooms the map to it, wherever the map was. Both versions are drawn on the one
  map, rather than two maps side by side or swiped across: a phone draws one map at a time.
- **The bar** under the toolbar names the earlier version as a row of roman pills, any earlier one to pick, and how
  much changed, which activates the summary: on a map, the features too (`1 feature moved, 1 added, 1 removed`).
- **Moving.** `j` and `k` step through the summary and the changes in page order; on a narrow screen each opens in
  the sheet, and the summary opens with the comparison. The toolbar's Open and All, and commenting on the page, wait
  until the comparison is left; selecting words and commenting leaves it, the comment on the page as it is.

## Catalogue

The list of artifacts is a reading column, at most 760 px: a title in Fraunces, newest first, each entry parted from
the next by a hairline. Under the title, in Instrument Sans and `muted`: the namespace, where it came from in `ink`
(its ticket), when it last changed, how many versions it has past one, and its open decisions: "Your answer is wanted"
in `accent` when one waits on the reader. The open threads' count sits at the right in `accent`; none is a muted
dash. The tokens page and signing in are the same column.

The demo, where a deployment publishes it, is its own catalogue at `/demo`, which anyone reads without signing in;
the catalogue at `/` leaves it out, and links to it, as the sign-in a reader is first asked for does.

**Filtered by origin.** Where an artifact came from, in its header, links to the catalogue filtered by it
(`?origin=`, the pairs as JSON): every artifact from its ticket, in the demo's catalogue for one of the demo's. The
title says what it is filtered by ("From PAY-142"), and under it, in Instrument Sans and `muted`, the pairs and "Every
artifact", the way back. Boards are left out: they are not filtered by origin. Nothing found says so, with the way back.

## Inbox

What is new to the signed-in person on the artifacts they take part in (REQUIREMENTS U11), at `/inbox`: the
catalogue's column and entries, newest news first, "Mark all read" at the title's right.

- **An entry** is the artifact's title, then in its meta line whether a version is new (`New to you` for one never
  opened, else the version), how many threads have news, and when the newest came. How many changes are new sits at
  the right in `accent`. Under it, its newest three changes, each on a `rule` hairline at its left: the passage in
  `muted` italics on one line, then the author's name in small caps and their words, three lines at most.
- **Opening an entry** opens the artifact at its newest news's thread. The page marks every thread with news for the
  reader "New", a label in `accent` above its first comment, for the rest of the visit; the toolbar counts them
  (`2 new`, in `accent`) and steps through them. Only an artifact the reader takes part in marks anything new.
- **The header** shows Inbox among the person's links, its count in `accent` when there is news; the catalogue says
  "New to you" in `accent` on an entry with news.
- **Empty**, it says so in a line of `muted`, and what would come there.

## Boards

A board is several artifacts on one canvas, each in a frame at a screen's size, as a design study hangs its directions
side by side (REQUIREMENTS U5). The canvas is the wall: the page's header and toolbar above it, and below them nothing
but the canvas, to the screen's edges, under one hairline.

- **A frame** shows its artifact's latest version as a screen of its size would, sandboxed like any artifact (L7), on
  `paper` with the frame's shadow. Above it, a label in Instrument Sans: the artifact's title in `ink`, the frame's
  size in `muted`, its open threads in `accent`. Labels and outlines keep one size on the screen at any zoom, and a
  label never runs past its frame's width: what does not fit ends in an ellipsis.
- **On a phone** (600 px and below on the screen's shorter side), two frames' pages are drawn at most, at any zoom:
  those nearest the middle of the screen, where the reader looks. Six pages at once are more than a phone has the
  memory for. The rest show their sheets and labels, and a frame's page fills in as the reader pans or zooms to it.
- **Moving.** Drag to pan, by pointer or by touch; pinch, the wheel, or the toolbar's zoom control (`−`, the zoom in
  percent, `+`, Fit) to zoom, about the cursor or the pinch's middle, from 5% to 100%: a frame's page at its own size,
  as a reader opens the frame to read it closer. The board opens fitted to the screen, and fits again on a resize until
  the reader moves it. Keys: `+` and `-` zoom, `0` fits, the arrows pan. The browser's own zoom is off on a board's
  page: only the canvas zooms, as a phone has not the memory to draw all its pages larger. While the zoom changes, a
  frame is its sheet and label alone, and its page is drawn again once the zoom is still: a phone cannot redraw every
  page at each step of a pinch.
- **Opening a frame.** A frame is read by opening it, never on the canvas: the canvas takes every pointer, and a
  frame's page is inert there. A tap or a click opens it on the artifact's page, at the frame's width when that is
  narrower than the page's, with its threads in the margin as on any artifact's page, and the way back to the board
  first in the toolbar. A drag that ends on a frame does not open it.
- **The design study's board**, `/directions/board`, is the same canvas over the repository's pages alone, so every
  deployment shows it, with no database and no demo: a frame opens its direction's own page, and nothing takes a
  comment.
- **The catalogue** lists boards above artifacts, in the same entries: the title, the namespace, how many frames, and
  the open threads at the right.

## Decisions

A decision is a question an agent asked on the artifact, for people to answer by choosing (REQUIREMENTS U11). It is
the one call to action Louvre makes, so it hangs above the artifact, in the artifact's column, before the reader
starts reading; the margin stays the conversation's.

- **A decision** has no box: a hairline above it, then a label row in Instrument Sans (Decision, or "Your answer is
  wanted" in `accent` when it asks the reader; who asked, an agent marked as in a thread; when), the question in
  Fraunces at a section head's size, and its options. One that waits on the reader carries an `accent` rule on its
  left, as an active thread does.
- **Options** are rows in Source Serif: a radio, or a checkbox where several may be chosen, in `accent` once checked;
  the label in `ink`; its detail under it in `muted`. An option about a passage lights that passage in the frame while
  it is hovered or focused, with the `hl-strong` band, and "Passage" at its right scrolls the page to it. An option
  about a place on a map Louvre draws lights it the same way, as a filled `accent` disc on the map, and "Place" at its
  right pans and zooms the map to it. The note is a single line that grows, as a reply is. Answering is the filled
  button: it is what the page asks for.
- **Results** show once the reader has answered, once it is closed, or to a reader who cannot answer: never before
  they choose, so the count does not sway them. Each option's count is a number and a hairline bar, `muted`, and
  `accent` for the reader's choice and the outcome, each tagged in `accent`. Answers follow as notes do in the
  margin: the name in small caps, the choice, the note under it.
- **Open or closed up.** An open decision shows whole; a closed one shows as its question and outcome, and opens on a
  tap. A link to it (`?decision=`) opens the page scrolled to it, shown whole.
- **Closing** is for whoever asked, or the person their agent writes for: Close, then the option decided on and why,
  in a row of small fields.
- **The list of decisions**, `/decisions`, is the catalogue's column: waiting on the reader, then open, then decided,
  each entry its question, its artifact in `ink`, who asked, when, and who it still waits on, the reader named "you".

## Louvre's style for agents

`louvre-1` (`louvre.core.style`, REQUIREMENTS U6) is this file's tokens and type for a page inside the frame: dark
first, light when the reader's system is, every color a custom property. It is set in Louvre's own faces, which Louvre
serves to its artifacts (D008); where a page is shown elsewhere, the reader's own serif and sans stand in. Until 1.0 it
is the one version, changed in place (D008); from 1.0 a later style is a new version beside it, a page that inlined
`louvre-1` keeps it, and its fonts stay served. A page Louvre draws itself, Markdown or GeoJSON, is drawn in the current
style each time it is shown.

Its files sit in `src/louvre/core/style/louvre-1/`: the stylesheet, its guide for agents (`rules.md`), and a starter
page for each kind of artifact, which together use every component it styles. A page needs more than Louvre's chrome
does, so it adds to these tokens, in both themes, each reading at 4.5:1 or better on its background and its cards:
`good` (`#6fbf8e`, `#2f7a4d`) and `bad` (`#e0915a`, `#a5521b`) for a change that is good or bad news. The accent
still marks what matters most, and no color says anything alone.

**Charts** are Marginalia (picked by the operator on 2026-10-24 over a palette of series colors with a legend, and
over the same look without notes), drawn by `louvre.core.style.chart` and handed to agents by `style_chart`. A chart
is a figure between hairlines, not in a card: its finding as its title in Fraunces, over what it measures in
Instrument Sans and `muted`. What it is about is in `accent`; every other series is `muted`, and every axis and
gridline a `rule` hairline. Each series is labeled where it is, in Source Serif italic, so there is no legend. The
moments that matter are numbered on the chart in `accent`, as threads are, and said under it in sentences a reader can
quote in a comment. Its source closes it. The SVG is 440 units wide, its text set larger on a phone.

**Maps** are drawn by the map kit (`louvre.core.maps`, `louvre-map-1`) in the same look, in a figure like a chart's.
The basemap is quiet: water is `bg`, land a mix of `card` and `rule`, borders a hairline, and cities in Noto Sans
italic, a step lighter than `muted`, the larger ones zoomed out and more zoomed in. The page's places are over it: what
the map is about in `accent`, filled; the rest hollow in `muted`. Each is labeled in Noto Sans, toward the map's middle
first so a place at its edge is labeled inside it, and numbered in `accent` as a chart's notes are. A key under the map
(`l-key`) says what the accent marks. The controls are cards with `rule` hairlines, the attribution and scale bar in
`muted`; a phone pans with two fingers, so one scrolls the page. The box is 22rem tall, 18rem on a phone.
Past a city's scale Natural Earth fades out, its coast a kilometre out there, and OpenStreetMap's streets fade in:
water in `bg`, buildings a step darker than the ground, roads a step above `rule` widening as the map zooms in, rail
and paths dashed, street names in Noto Sans italic. A page's own `context` is drawn as the roads are. Both are always
quieter than the data, whose lines widen with them.

**GeoJSON** an agent publishes is drawn by Louvre as a page in the house style (`louvre.core.geodata`): a kicker
counting its features, the title, the lede, the map with its key, then "Each feature", a numbered list of each
feature's label in bold and its properties flowing after it, each name small and muted before its value. Those are
the page's words, which threads are on. A tap on a feature opens a card with the same, its label linking to its row;
its words are drawn by CSS so that no passage is ever found in the card.

## Not decided yet

- A comment pinned to a point on a board's canvas rather than to a frame's words (REQUIREMENTS, Open).
- A decision across a board's frames, each frame an option (REQUIREMENTS, Open).
- How two versions compare on a page, and on a phone (REQUIREMENTS U8).
- How a thread on a place shows on the map and in the margin (REQUIREMENTS U10).
