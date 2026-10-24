"""Boards: several artifacts on one canvas, each a frame at a size and a place of its own (REQUIREMENTS U5).

Over mock data for now (roadmap M3): a board is written down in code, as the demo's design study is, and finds each
frame's artifact by its origin, in the board's namespace, through the reader's store, so a reader sees only the frames
whose artifacts they reach. Whether an agent composes a board, and how canopy's contract would say so, is open
(REQUIREMENTS, Open).
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from louvre.core.store import Code, Refused, Store


@dataclass(frozen=True)
class Frame:
    """One artifact on a board: its latest version, shown at a screen's size, at a place on the canvas."""

    #: Unique on its board, for the link that opens it.
    id: str
    #: What the board calls it beside its artifact's title, such as `Phone, 390`.
    label: str
    #: Pairs its artifact's origin holds, which find it in the board's namespace: the newest, when several do.
    origin: Mapping[str, str]
    #: Where its top left corner is on the canvas, in CSS pixels.
    x: int
    y: int
    #: The size it is shown at, in CSS pixels: the page inside lays itself out as on a screen this size.
    width: int
    height: int


@dataclass(frozen=True)
class Board:
    """Several artifacts on one canvas, to pan and zoom across."""

    #: Stable, for its page's URL.
    id: str
    title: str
    #: Where its frames' artifacts are found.
    namespace: str
    frames: Sequence[Frame]


def listing(store: Store, boards: Iterable[Board]) -> list[dict[str, object]]:
    """List the boards with a frame whose artifact the store reaches.

    Returns:
        Each board, with how many of its frames the store reaches and how many open threads their artifacts have.
    """
    listed: list[dict[str, object]] = []
    for board in boards:
        frames = _frames(store, board)
        if not frames:
            continue
        artifacts = {str(a["id"]): a for f in frames if isinstance(a := f["artifact"], dict)}
        listed.append(
            {
                **_board_json(board),
                "frames": len(frames),
                "open_threads": sum(int(str(a["open_threads"])) for a in artifacts.values()),
            },
        )
    return listed


def shown(store: Store, boards: Iterable[Board], board_id: str) -> dict[str, object]:
    """Show a board: each frame the store reaches, with its artifact.

    Returns:
        The board, and its frames in the order it lists them.

    Raises:
        Refused: `not_found` for no board by that id.
    """
    board = next((b for b in boards if b.id == board_id), None)
    if board is None:
        raise Refused(Code.NOT_FOUND, f"no board {board_id!r}")
    return {"board": _board_json(board), "frames": _frames(store, board)}


def _frames(store: Store, board: Board) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for frame in board.frames:
        artifacts = store.overview(origin=frame.origin, namespace=board.namespace)["artifacts"]
        if isinstance(artifacts, list) and artifacts:
            found.append(
                {
                    "id": frame.id,
                    "label": frame.label,
                    "x": frame.x,
                    "y": frame.y,
                    "width": frame.width,
                    "height": frame.height,
                    "artifact": artifacts[0],
                },
            )
    return found


def _board_json(board: Board) -> dict[str, object]:
    return {"id": board.id, "title": board.title, "namespace": board.namespace}
