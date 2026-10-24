# M8. Comparing versions

REQUIREMENTS U8, U4, L2, D008. A reader sees what changed between two versions of an artifact, and what happened to
its threads in between.

- On an artifact's page, a control picks two versions, the latest and the one before it unless the reader picks
  others; a link to the comparison (`?compare=3..4`) opens it.
- What changed is read from the visible text both sides already read (L2), word by word, so an HTML artifact's markup
  and scripts never show as changes. The later version stays in its frame, its added words lit by the bridge as a
  passage is (D008); the margin lists each change, its removed words and its added ones, and a tap scrolls the frame
  to it. On a phone the list is a sheet over the page, as threads are.
- Each thread shows what happened to it between the two: replied to, resolved, or `passage_gone` where its words left.
- Nothing in the contract changes: comparing is the web's alone.

Accept: on a phone and a laptop, the operator compares two versions of the demo's revised report, reads what changed,
and finds the thread the revision answered; Playwright holds the comparison, and the screen matrix holds it at every
size.

Status: not started.
