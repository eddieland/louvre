# Directions, 2026-10-23

Three looks for Louvre's artifact page, for the operator to pick from (ROADMAP M1). Each is one static HTML file with
no build step: open it in a browser. Each shows the same artifact and the same threads, and the margin-thread
interaction works the same way in all three. Mock data only, so nothing is saved, and only version 3 is drawn.

| File | Direction | What it tries |
|---|---|---|
| [gallery.html](gallery.html) | Gallery | The artifact is the exhibit, hung on a warm wall. Serif type, generous space, and threads as placards beside it. Calm, and close to the name. |
| [studio.html](studio.html) | Studio | A working tool. Dark chrome around a bright page, threads as cards with faces, state always in view, and keyboard hints. Familiar from Figma, Linear, and Google Docs. |
| [margins.html](margins.html) | Margins | Almost no chrome. One column of text, and the conversation set as marginalia beside it, numbered like sidenotes. The most reading-first. |

## What to try in each

- Hover a thread: its passage lights up. Hover a passage: its thread does.
- Click a passage: its thread opens with a reply box, and the threads around it move aside so it sits level with its
  passage.
- Select a few words: a Comment button appears beside them, in the margin on a wide screen. Click it, or press `c`,
  and a new thread opens there. Ctrl Enter posts it.
- Resolve a thread: it leaves the margin, with an Undo. "All" brings resolved threads back.
- `j` and `k` move between threads; Escape closes one.
- The thread whose passage was reworded out of version 3 (`passage_gone`) waits below the others, never moved to other
  words. The toolbar's notice jumps to it.
- On a phone, the margin becomes a bottom sheet: tap a passage to read its thread.

## Common to all three

- Every agent comment is marked as an agent's, on behalf of the person whose token it used, apart from a person's.
- A thread stays level with its passage; when two would overlap, the active one keeps its place and the others move.

## Not decided here

- Dark themes. The chosen direction gets both, as tokens, in `ui/DESIGN.md`.
- The artifact list, sign-in, and tokens pages: M2 designs them in the chosen direction.
- How the margin learns where a passage is once the artifact's HTML renders in its own sandboxed frame, on its own
  origin, as it must (REQUIREMENTS L7). Here the artifact sits inline. M2 measures anchors inside the frame and posts
  their positions out.
