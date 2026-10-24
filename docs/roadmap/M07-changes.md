# M7. Changes between versions

REQUIREMENTS U7, U4, L2, L7. The page a reviewer opens when an agent answers their comments with a new version: what it
changed, marked in place, and what became of each thread.

- The store compares two versions' texts word by word, quickly on the longest page it holds, and anchors each change
  in the later version as a thread is anchored, so the bridge finds and marks it.
- The artifact's page compares the version shown with an earlier one: the changed words marked in the sandboxed frame,
  a note for each in the margin level with it, and a summary of the earlier threads' passages, states, and replies.
- A comparison is a link, and every screen in the matrix holds it.

Accept: on a phone and a laptop, the operator opens the demo's report, compares its versions, steps through the
changes, sees what became of each thread, and opens one from the summary; Playwright holds each of those steps, and the
screen matrix holds the comparison at every size.

Status: in progress: built at the operator's word (2026-10-24), ahead of M6, as M3 was ahead of M2; waiting on the
operator's pass on a phone and a laptop. `louvre.core.compare` compares texts in two passes, by chunks of words and
then word by word inside the chunks that differ, so a page of 300,000 words compares in under a second; Hypothesis holds
that putting back what each change removed rebuilds the earlier text. Playwright holds comparing, stepping, and opening
a thread from the summary (`tests/louvre/web/test_flows.py`).
