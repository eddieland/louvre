# M18. Deleting and forgetting

REQUIREMENTS L6, L8, Open, D012; M3's "not built". What leaves Louvre, and when, once a person says so; no tool ever
deletes (L1).

- Deleting a board on the web, by its owner, as an artifact is deleted; its frames' artifacts stay.
- A deleted artifact stops being served at once, its versions, its files, and the key that reached them included
  (D012, Revisit), and its threads leave the feed as the contract says of a deleted thing; its rows go later, by
  `louvre prune`, which a deployment schedules, since Louvre keeps no worker (D010).
- What Louvre keeps of an artifact whose ticket canopy forgets (Open, from canopy's list): everything, until a person
  says otherwise. The ticket's list (M2) offers its owner one act over all of a ticket's artifacts, so forgetting a
  ticket in Louvre is one tap, never a tool's.
- A token revoked, or its owner's account closed by the deployment's allowlist, reads and writes nothing more, and
  what it published stays, its author stable (L4).

Accept: the operator deletes a board and an artifact with files; the files' path answers nothing to a reader who has
it, the feed says what left, and after `louvre prune` the rows are gone; a ticket's artifacts leave in one act.

Status: proposed 2026-11-07, for the operator to order or strike; not started.
