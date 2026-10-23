# M1. The contract in process

REQUIREMENTS L1, L2, L3. The store's behavior as a library, before any network: what every later milestone serves.

- Records as the contract names them: artifacts with origin keys, immutable versions, threads, comments, and authors.
- A version's visible text, read from HTML or Markdown as the contract says, and anchors resolved against it by their
  words, `passage_gone` where they are found nowhere.
- The eight tools as functions over the store, with the contract's results and refusal codes, a caller's namespace
  and scopes passed in.
- The comment feed: one `seq` in commit order, pages ending with an `end` line, filtered by origin.
- Postgres behind the store (D007), its schema in numbered migrations, and a Postgres in CI for the tests.

Accept: tests hold each tool to the contract: a new version keeps a thread's anchor and a reworded passage reads
`passage_gone`; the feed's cursor misses no change and repeats none across pages; each refusal code is given where
the contract says.

Status: not started.
