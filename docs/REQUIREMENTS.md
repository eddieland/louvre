# Louvre requirements

What Louvre must do, written down 2026-10-23 from what canopy needs of it, and where Louvre stands on each. canopy's
design is the source: [DESIGN §38](https://github.com/eddieland/canopy/blob/main/docs/design/ARTIFACTS.md), its
requirement R26, and the contract both stores serve, the
[local store's README](https://github.com/eddieland/canopy/blob/main/packages/canopy-artifacts/README.md). Where this
file and that contract disagree, the contract wins until the operator settles it here.

Status words: **Built** (in code with tests), **Planned** (in a roadmap milestone, not built), **Gap** (nothing planned
yet).

## The contract

### L1. Serve the artifacts contract's eight tools over MCP's streamable HTTP

Planned (M1, M2). `artifact_publish`, `artifact_read`, `artifact_list`, `thread_list`, `comment_feed`,
`comment_reply`, `comment_create`, and `thread_resolve`, with the inputs, results, and refusal codes the contract
names, so a skill written against canopy's local store works against Louvre unchanged. No tool deletes an artifact or
changes who may see it.

### L2. Versions keep their threads, and anchors are words, never positions

Planned (M1). A revision is a new version of the same artifact. A thread is anchored by a `TextQuoteSelector` over a
version's visible text; on a new version it is found again by its words, and words found nowhere read `passage_gone`
and never move to other words. HTML anchors are taken inside the sandboxed frame and checked against that text.

### L3. A comment feed a reader can trust

Planned (M1). One `seq` across the store, given in commit order and only once a change is visible, so nothing appears
below a cursor a reader has passed; paged, each page ending with an `end` line, so a feed cut short never reads as
comments gone. Filtered by origin keys the publisher set, which Louvre keeps and never interprets.

### L4. Who wrote each comment

Planned (M2, M3). Each comment's author is an id Louvre authenticated, stable for the life of the account. A comment
written with a token is `kind: agent`, on behalf of the person who minted it; only one written through the web by a
signed-in person is `kind: person`. Louvre states the fact; whether a comment carries authority is its reader's call.

## Tokens and scope

### L5. Tokens bound to an account and one namespace

Planned (M2). A person mints a token bound to their account and one namespace, with scopes `read`, `publish`, and
`comment`. A token reads, publishes, and comments only within its namespace, and is refused `out_of_scope` outside
it and `read_only` for a write its scopes lack. This bounds what an agent steered by what it read can leak or deface.

## The web

### L6. People sign in, read, and comment

Planned (M3). A signed-in person reads an artifact's versions and comments on its passages (`via: web`), edits and
deletes their comments, and resolves threads. People, never tokens, delete an artifact or change who may see it.

### L7. An artifact's HTML is untrusted content

Planned (M3). It renders only on an origin of its own, in a sandboxed frame without same-origin access, never on the
origin that holds a person's session. A comment's text is text.

## Constraints

### C1. Louvre never calls its readers

Built (nothing calls out). canopy pulls the feed on its own schedule and runs no listener for an outside system.
Louvre may offer webhooks to others later; canopy does not use them.

## Open

To settle before the milestone that needs it:

- Where Louvre runs and what holds its data: a managed database, or SQLite on one host (M1 needs the answer for its
  storage, M4 for deployment).
- How people sign in: the organization's identity provider, or GitHub (M3).
- Who may read an artifact: everyone in the organization, or a namespace's members (M3).
- From canopy's open list: whether Louvre's design system is public on npm or internal; what Louvre keeps of an
  artifact whose ticket canopy forgets; and whether Louvre is the name.
