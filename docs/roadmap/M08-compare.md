# M8. Comparing versions

REQUIREMENTS U8, U4, L2, D008. A reader sees what a version changed since an earlier one, and what became of its
threads in between.

- A Changes toggle on any version after the first, against the version before it unless the reader picks another; a
  link to the comparison (`?changes=N`) opens it.
- What changed is read from the visible text both sides already read (L2), so an HTML artifact's markup and scripts
  never show as changes. The version stays in its frame, in its author's look, its added and rewritten words lit by
  the bridge (D008); a removal is noted where its words were, never painted. The margin notes each change beside its
  passage; on a phone the notes open in the sheet, as threads do.
- The margin's summary says what became of each earlier thread: its passage unchanged, changed beside it, reworded or
  removed, resolved, or replied to since.
- Nothing in the contract changes: comparing is the web's alone (L1).

Accept: on a phone and a laptop, the operator compares two versions of the demo's revised report, reads what changed,
and finds the thread the revision answered; Playwright holds the comparison, and the screen matrix holds it at every
size.

Status: in progress: built (#30); waiting on the operator's pass on a phone and a laptop. `louvre.core.compare`
compares texts in two passes, by chunks of words and then word by word inside the chunks that differ, so a page of
300,000 words compares in under a second; Hypothesis holds that putting back what each change removed rebuilds the
earlier text. Playwright holds comparing, stepping through the changes, and opening a thread from the summary
(`tests/louvre/web/test_flows.py`), and the screen matrix holds the comparison.
