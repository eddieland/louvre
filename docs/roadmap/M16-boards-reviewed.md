# M16. Boards reviewed

REQUIREMENTS U5, U7, L2, D008, Open; `ui/DESIGN.md`, Not decided yet. Deciding and commenting across a board's frames,
as M13 did on maps, and people asking decisions as agents do.

- A decision across a board's frames, each frame an option (Open): the asker names frames in place of passages, an
  option lights its frame on the canvas while hovered or focused, and its link pans and zooms to it. It is answered on
  the board's page as on an artifact's; on a phone, in the sheet.
- A comment pinned to a point on the canvas (Open), held to L2 as a place on a map is (M12): the pin names a frame and
  a point in it as fractions of the frame's size, its words the frame's label, so a reader of `thread_list` that
  knows only words reads it unchanged (D011). It moves with its frame when the board is laid out again, and reads
  `passage_gone` when the frame's artifact leaves the board, never moving to another frame.
- People ask decisions on the web as agents do (Open): from passages they select on an artifact, or frames on a
  board, naming who it asks; an agent reads it over MCP as any decision, and whoever asked closes it.
- The kit's and the bridge's halves report a pin as they report a tap, and Louvre trusts them no further (D008).

Accept: on a phone and a laptop, the operator answers a decision whose options are a board's frames, pins a comment on
a frame, which an agent reads over MCP with its words, and asks a decision on the web that an agent reads from
`decision_feed` and closes.

Status: proposed 2026-11-07, for the operator to order or strike; not started. Whether a pin is wanted at all, or a
frame's words are enough, is the operator's to settle first (`ui/DESIGN.md`).
