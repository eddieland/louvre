# M4. The contract on Postgres, under the UI

REQUIREMENTS L1, L2, L3. The store's behavior as a library, which M2's UI then runs on in place of its mock data.

- Records as the contract names them: artifacts with origin keys, immutable versions, threads, comments, and authors.
- A version's visible text, read from HTML or Markdown as the contract says, and anchors resolved against it by their
  words, `passage_gone` where they are found nowhere.
- The eight tools as functions over the store, with the contract's results and refusal codes, a caller's namespace
  and scopes passed in.
- The comment feed: one `seq` in commit order, pages ending with an `end` line, filtered by origin.
- Postgres behind the store (D007), its schema in numbered migrations, and a Postgres in CI for the tests.
  The operator's storage rules (2026-10-23), for text artifacts that are Markdown or static HTML:
  - A version's content lives in a table of its own, apart from the version's metadata: a mutable or often-read field
    on the same row as a large body makes Postgres rewrite the body on every change.
  - A small `artifacts` table (the contract's name for the operator's "documents") holds a `current_version_id`
    pointer to the latest version. It is the one row that is updated, and it holds no content.
  - Versions are append-only: a new version is an insert, never an update. The artifact row, comments, and threads are
    not append-only: L6 lets a person edit and delete their comments and delete an artifact.
  - Each version's content is hashed (SHA-256). The hash skips inserting a version identical to the current one and
    doubles as an ETag. What `artifact_publish` returns when it skips an insert is to be read from canopy's contract
    before this milestone starts: it may expect a new version each time.
  - The content column is compressed with lz4, not Postgres's default. That needs Postgres 14 or later built with lz4,
    which the managed Postgres picked in M6 must have.
  - An index on `(artifact_id, version DESC)` serves the latest-version and history queries. The feed's `seq` (L3) gets
    its own.
  - A query that scans many rows (listing, search, history, the feed) reads no content; it joins to the content table
    only where the body is needed.
  - Every version is a full copy, on purpose. Diff storage, partitioning, and offloading content to object storage are
    not needed now, and are raised only on a concrete reason.
- M2's API served from the store, with the mock data kept for the UI's tests and a demo.

Accept: tests hold each tool to the contract: a new version keeps a thread's anchor and a reworded passage reads
`passage_gone`; the feed's cursor misses no change and repeats none across pages; each refusal code is given where
the contract says; M2's Playwright tests pass against the store.

Status: not started.
