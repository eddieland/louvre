# M3. Boards, over mock data

REQUIREMENTS U5, U4, L7. Several artifacts on one canvas, as a design study puts its directions side by side.

- A board's page: its frames laid out on a canvas, each an artifact's version at a size of its own, such as a phone's
  or a laptop's, running sandboxed.
- Pan and zoom by touch (drag, pinch) and by pointer (drag, wheel, a zoom control), fit to screen, and a frame opened to
  read whole, with its threads in the margin as on an artifact's page.
- Mock data first, as M2: the 2026-10-23 design study is the first board.

Accept: on a phone and a laptop, the operator pans and zooms across the design-study board, opens a frame, and
comments on it; the screen matrix holds the board at every size.

Status: in progress: built, over mock data as planned for the board and over the store for its frames' artifacts,
at the operator's word to build it before M2 is accepted (2026-10-24); waiting on the operator's pass on a phone and a
laptop. An agent publishes a board of its own artifacts with `board_publish` (D011), stored beside them
(`louvre.core.boards`), built 2026-10-29. The demo's board is `louvre.core.demo.BOARD`, served at `/b/design-study`;
Playwright holds panning, zooming, and opening a frame to comment, by pointer and by touch, and an agent's board
opened from the catalogue (`tests/louvre/web/test_flows.py`), and the screen matrix holds the board and a frame opened
from it. The same study is a board at `/directions/board` from the repository's pages
alone, to try on a deployment with no database or demo. Not built: deleting a board, or canopy's contract taking boards
(REQUIREMENTS, Open).
