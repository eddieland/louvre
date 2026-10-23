# Louvre requirements

What Louvre must do, written down 2026-10-23 from what canopy needs of it, and where Louvre stands on each. canopy's
design is the source: [DESIGN §38](https://github.com/eddieland/canopy/blob/main/docs/design/ARTIFACTS.md), its
requirement R26, and the contract both stores serve, the
[local store's README](https://github.com/eddieland/canopy/blob/main/packages/canopy-artifacts/README.md). Where this
file and that contract disagree, the contract wins until the operator settles it here.

Status words: **Built** (in code with tests), **Planned** (in a roadmap milestone, not built), **Gap** (nothing planned
yet).

## The experience

### U1. The UI and the interaction matter most

Planned (M1, M2). The operator's priority (2026-10-23): reading an artifact and commenting on it should feel right
before anything else is built, so the UI is built first, over mock data, and the store comes under it. Comments are
margin threads, as in a shared document: select words, and a thread opens in the margin beside its passage; threads
stack along the page and follow it as it scrolls. The look, picked from mock-ups in M1, is Annotated (`ui/DESIGN.md`).

### U2. Dark first

Planned (M1, M2). The operator works in dark mode (2026-10-23): every Louvre page is designed dark first, with light as
the second theme, both from the same tokens. An artifact keeps its author's look: Louvre does not restyle it, and the
viewer's color scheme reaches its frame, so an artifact that supports both follows the reader.

### U3. Rich artifacts render as their authors made them

Planned (M2). The operator expects agents to publish designed pages (2026-10-23), such as a polished HTML report: its
own styles, fonts, inline SVG, images, charts, and scripts for interaction. Louvre renders it whole, scripts running,
inside the sandbox L7 requires, and its threads anchor on its visible words as any artifact's do. The preview
deployment serves one such report (#4).

### U4. Every page works on every screen

Planned (M1, M2). The operator's priority (2026-10-23): Louvre works well from a small phone to a wide desktop, by
touch and by pointer. Every page is checked at each size in the screen matrix, dark first, for sideways scrolling and
errors, and its screenshots are checked in as the record of how it looks there (`docs/screenshots/`).

### U5. Boards: several artifacts on one canvas to pan and zoom

Planned (M3). The operator's example (2026-10-23): a design study, three directions each at a phone's and a laptop's
size, is the kind of thing Louvre should serve. An agent composes a board from artifacts it published, each a frame at
a size and place on one canvas, and the reader pans and zooms across it, by touch and by pointer, opens a frame to read
it whole, and comments on a frame's passages as on any artifact's. A board's frames run sandboxed, each on its own
(L7).

### U6. Louvre's style, for agents that want it

Planned (M2, M5). The operator wants agents to reuse Louvre's styles and practices in what they publish, when they
choose to (2026-10-23). Louvre is the source of it: a versioned stylesheet, dark and light from the same tokens, with
its components (a report's header, figures, callouts, tables) and the rules for using them. Agents get it over the MCP
server they already reach Louvre by, so nothing is installed and it never lags Louvre; a skill only says when to use
it. An artifact that opts in names a version, so a later style never restyles a published page.

## The contract

### L1. Serve the artifacts contract's eight tools over MCP's streamable HTTP

Planned (M4, M5). `artifact_publish`, `artifact_read`, `artifact_list`, `thread_list`, `comment_feed`,
`comment_reply`, `comment_create`, and `thread_resolve`, with the inputs, results, and refusal codes the contract
names, so a skill written against canopy's local store works against Louvre unchanged. No tool deletes an artifact or
changes who may see it.

### L2. Versions keep their threads, and anchors are words, never positions

Planned (M2, M4). A revision is a new version of the same artifact. A thread is anchored by a `TextQuoteSelector` over a
version's visible text; on a new version it is found again by its words, and words found nowhere read `passage_gone`
and never move to other words. HTML anchors are taken inside the sandboxed frame and checked against that text.

### L3. A comment feed a reader can trust

Planned (M4). One `seq` across the store, given in commit order and only once a change is visible, so nothing appears
below a cursor a reader has passed; paged, each page ending with an `end` line, so a feed cut short never reads as
comments gone. Filtered by origin keys the publisher set, which Louvre keeps and never interprets.

### L4. Who wrote each comment

Planned (M2, M5). Each comment's author is an id Louvre authenticated, stable for the life of the account. A comment
written with a token is `kind: agent`, on behalf of the person who minted it; only one written through the web by a
signed-in person is `kind: person`. Louvre states the fact; whether a comment carries authority is its reader's call.

## Tokens and scope

### L5. Tokens bound to an account and one namespace

Planned (M5). A person mints a token bound to their account and one namespace, with scopes `read`, `publish`, and
`comment`. A token reads, publishes, and comments only within its namespace, and is refused `out_of_scope` outside
it and `read_only` for a write its scopes lack. This bounds what an agent steered by what it read can leak or deface.

## The web

### L6. People sign in, read, and comment

Planned (M2, M5). A signed-in person reads an artifact's versions and comments on its passages (`via: web`), edits and
deletes their comments, and resolves threads. People, never tokens, delete an artifact or change who may see it.

### L7. An artifact's HTML is untrusted content

Planned (M2). It renders only on an origin of its own, in a sandboxed frame without same-origin access, never on the
origin that holds a person's session. A comment's text is text.

## Constraints

### C1. Louvre never calls its readers

Built (nothing calls out). canopy pulls the feed on its own schedule and runs no listener for an outside system.
Louvre may offer webhooks to others later; canopy does not use them.

## Open

To settle before the milestone that needs it:

- Where Louvre runs, with a managed Postgres (D007): a preview runs on Vercel from the start (#4), and whether
  production stays there is open (M6).
- How people sign in: the organization's identity provider, or GitHub (M5).
- Who may read an artifact: everyone in the organization, or a namespace's members (M5).
- Whether a board is an artifact of its own content type, which grows canopy's contract, and whether a comment may be
  pinned to a point on the canvas rather than to a frame's words (U5, M3).
- How an artifact opts into Louvre's style: links a stylesheet Louvre serves to artifacts at a pinned version, which
  the artifact policy must then allow, or inlines what the MCP tool returns (U6, M2).
- Whether an artifact may load from the network (a CDN's script, a web font, a remote image), or must carry everything
  inline or in files published with it. The contract has one `content` string per version, so files beside it would
  grow canopy's contract too (U3, M2).
- From canopy's open list: whether Louvre's design system is public on npm or internal; what Louvre keeps of an
  artifact whose ticket canopy forgets; and whether Louvre is the name.
