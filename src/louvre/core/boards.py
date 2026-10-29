"""Boards: several artifacts on one canvas, each a frame at a size and a place of its own (REQUIREMENTS U5).

An agent publishes a board of artifacts it published, with `board_publish`, a tool of Louvre's own (D011): rows of
frames, each an artifact shown at its latest version at a screen's size, under a label, which Louvre lays out a row at
a time, `GAP` apart. A board is in its agent's namespace, and its frames' artifacts are too. A board published again
by its id takes its new title and frames, and keeps its origin; it keeps no versions, since nothing is anchored on it:
its threads are its frames' artifacts'.

The demo's boards are written down in code (louvre.core.demo) and find each frame's artifact by its origin instead.
Either way a board finds its frames' artifacts through the reader's store, so a reader sees only the frames whose
artifacts they reach, and only the boards with one.
"""

import json
import secrets
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from louvre.core.store import (
    MAX_TITLE,
    Code,
    Permission,
    Refused,
    Row,
    Store,
    bounded,
    check_origin,
)

#: The space between a published board's frames, in CSS pixels: wide enough for a frame's label above it.
GAP = 160
#: The most frames a published board holds: no more artifacts than a page of the store's list, which finds them.
MAX_FRAMES = 48
#: The most characters of a frame's label.
MAX_LABEL = 60
#: The narrowest and the widest a frame is shown, and the shortest and the tallest, in CSS pixels: a small phone's
#: screen to a wide desktop's, and a page's height scrolled to several screens.
MIN_WIDTH = 280
MAX_WIDTH = 3840
MIN_HEIGHT = 280
MAX_HEIGHT = 8000
#: The most boards a list holds: the newest.
LIST_MOST = 50


@dataclass(frozen=True)
class Frame:
    """One artifact on a board: its latest version, shown at a screen's size, at a place on the canvas."""

    #: Unique on its board, for the link that opens it.
    id: str
    #: What the board calls it beside its artifact's title, such as `Phone, 390`.
    label: str
    #: Pairs its artifact's origin holds, which find it in the board's namespace: the newest, when several do. Empty
    #: for a frame that names its artifact.
    origin: Mapping[str, str]
    #: Where its top left corner is on the canvas, in CSS pixels.
    x: int
    y: int
    #: The size it is shown at, in CSS pixels: the page inside lays itself out as on a screen this size.
    width: int
    height: int
    #: The artifact it shows, by id, as a published board's frames name theirs; None to find it by `origin`.
    artifact_id: str | None = None


@dataclass(frozen=True)
class Board:
    """Several artifacts on one canvas, to pan and zoom across."""

    #: Stable, for its page's URL.
    id: str
    title: str
    #: Where its frames' artifacts are found.
    namespace: str
    frames: Sequence[Frame]
    #: Pairs its publisher set when it was made, as an artifact's origin is; empty for the demo's.
    origin: Mapping[str, str] = field(default_factory=dict[str, str])


@dataclass(frozen=True)
class Framed:
    """An artifact as an agent puts it on a board it publishes: at a screen's size, under a label."""

    #: The artifact, in the board's namespace; the frame shows its latest version.
    artifact_id: str
    #: What the board calls it beside its artifact's title, such as `Phone, 390`.
    label: str
    #: The size it is shown at, in CSS pixels.
    width: int
    height: int


class Boards:
    """The boards agents publish, in the namespaces a store's scope reaches, held to it as its other records are."""

    def __init__(self, store: Store) -> None:
        """Serve the boards `store` reaches."""
        self._store = store
        self._conn = store.connection

    def publish(
        self,
        *,
        title: str,
        rows: Sequence[Sequence[Framed]],
        origin: Mapping[str, str] | None = None,
        board_id: str | None = None,
    ) -> dict[str, object]:
        """Make a board in the scope's home namespace, or with `board_id`, give one a new title and frames.

        Its frames are laid out a row at a time, left to right, each row under the tallest frame of the row before.

        Returns:
            Its id, how many frames it has, and the url of its page.

        Raises:
            Refused: `read_only` without publish; `invalid` for a blank title or label, no frames, an empty row, a size
                out of bounds, or an origin given with `board_id`; `too_long` for a title, label, origin, or list of
                frames over its bound; `not_found` or `out_of_scope` for `board_id`, or for a frame's artifact, which
                must be in the scope's home namespace.
        """
        store = self._store
        store.require(Permission.PUBLISH)
        home = store.scope.home
        if home is None:
            raise Refused(Code.READ_ONLY, "this scope publishes nowhere")
        if not title.strip():
            raise Refused(Code.INVALID, "a board's title must not be blank")
        bounded("title", title, MAX_TITLE)
        if board_id is not None and origin:
            raise Refused(Code.INVALID, "a board's origin is set when it is made; omit it to publish it again")
        frames = _laid_out(rows)
        pairs = check_origin({**(origin or {}), **store.scope.origin}) if board_id is None else {}
        now = datetime.now(UTC)
        with store.writing():
            for artifact_id in dict.fromkeys(f.artifact_id for f in frames if f.artifact_id is not None):
                if store.artifact_row(artifact_id)["namespace"] != home:
                    raise Refused(Code.OUT_OF_SCOPE, f"{artifact_id} is not in {home}, where the board is")
            listed = json.dumps([_frame_json(f) for f in frames])
            if board_id is None:
                board_id = f"b_{secrets.token_hex(8)}"
                self._conn.execute(
                    "INSERT INTO boards (id, namespace, title, origin, frames, owner_id, created_at, updated_at)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (board_id, home, title, json.dumps(pairs), listed, store.scope.account_id, now, now),
                )
            else:
                self._row(board_id, locked=True)
                self._conn.execute(
                    "UPDATE boards SET title = %s, frames = %s, updated_at = %s WHERE id = %s",
                    (title, listed, now, board_id),
                )
        return {"board_id": board_id, "frames": len(frames), "url": f"{store.base_url}/b/{board_id}"}

    def listed(self) -> list[Board]:
        """List the published boards in the namespaces the scope reaches, newest first.

        Returns:
            At most `LIST_MOST` boards.
        """
        with self._store.reading():
            rows = self._conn.execute(
                "SELECT * FROM boards b WHERE (%(all)s OR b.namespace = ANY(%(namespaces)s))"
                " ORDER BY b.n DESC LIMIT %(limit)s",
                {"limit": LIST_MOST} | self._store.reach(),
            ).fetchall()
        return [_board(row) for row in rows]

    def find(self, board_id: str) -> Board | None:
        """Find a published board by its id.

        Returns:
            The board, or None for no board by that id.

        Raises:
            Refused: `out_of_scope` for a board outside the namespaces the scope reaches.
        """
        with self._store.reading():
            row = self._conn.execute("SELECT * FROM boards WHERE id = %s", (board_id,)).fetchone()
            if row is None:
                return None
            self._store.reaches(str(row["namespace"]), board_id)
        return _board(row)

    def _row(self, board_id: str, *, locked: bool = False) -> Row:
        """Find a published board the scope reaches, inside a write, and lock its row until it commits if `locked`.

        Returns:
            Its row.

        Raises:
            Refused: `not_found` for no such board, `out_of_scope` for one outside the scope.
        """
        row = self._conn.execute(
            "SELECT * FROM boards WHERE id = %s"  # noqa: S608  (constant SQL; values are bound)
            + (" FOR NO KEY UPDATE" if locked else ""),
            (board_id,),
        ).fetchone()
        if row is None:
            raise Refused(Code.NOT_FOUND, f"no board {board_id!r}")
        self._store.reaches(str(row["namespace"]), board_id)
        return row


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


def _laid_out(rows: Sequence[Sequence[Framed]]) -> list[Frame]:
    """Check a board's rows of frames, and lay them out on its canvas, each row under the tallest of the one before.

    Returns:
        The frames, in the rows' order, their ids `f1`, `f2`, and on.

    Raises:
        Refused: `invalid` for no frames, an empty row, a blank label, or a size out of bounds; `too_long` for more
            than `MAX_FRAMES` frames or a label over its bound.
    """
    count = sum(len(row) for row in rows)
    if count == 0:
        raise Refused(Code.INVALID, "a board holds at least one frame")
    if count > MAX_FRAMES:
        raise Refused(Code.TOO_LONG, f"the board has {count} frames; at most {MAX_FRAMES}")
    frames: list[Frame] = []
    y = 0
    for row in rows:
        if not row:
            raise Refused(Code.INVALID, "a board's row holds at least one frame")
        x = 0
        for framed in row:
            _check_frame(framed)
            frames.append(
                Frame(
                    f"f{len(frames) + 1}",
                    framed.label,
                    {},
                    x,
                    y,
                    framed.width,
                    framed.height,
                    framed.artifact_id,
                ),
            )
            x += framed.width + GAP
        y += max(f.height for f in row) + GAP
    return frames


def _check_frame(framed: Framed) -> None:
    """Hold a frame to its bounds.

    Raises:
        Refused: `invalid` for a blank label or a size out of bounds, `too_long` for a label over its bound.
    """
    if not framed.label.strip():
        raise Refused(Code.INVALID, "a frame's label must not be blank")
    bounded("frame's label", framed.label, MAX_LABEL)
    if not MIN_WIDTH <= framed.width <= MAX_WIDTH:
        raise Refused(Code.INVALID, f"a frame is {MIN_WIDTH} to {MAX_WIDTH} pixels wide, not {framed.width}")
    if not MIN_HEIGHT <= framed.height <= MAX_HEIGHT:
        raise Refused(Code.INVALID, f"a frame is {MIN_HEIGHT} to {MAX_HEIGHT} pixels tall, not {framed.height}")


def _frames(store: Store, board: Board) -> list[dict[str, object]]:
    named = {f.artifact_id for f in board.frames if f.artifact_id is not None}
    by_id: dict[str, object] = {}
    if named:
        artifacts = store.overview(namespace=board.namespace, ids=named)["artifacts"]
        by_id = {str(a["id"]): a for a in artifacts if isinstance(a, dict)} if isinstance(artifacts, list) else {}
    found: list[dict[str, object]] = []
    for frame in board.frames:
        if frame.artifact_id is not None:
            artifact = by_id.get(frame.artifact_id)
        else:
            artifacts = store.overview(origin=frame.origin, namespace=board.namespace)["artifacts"]
            artifact = artifacts[0] if isinstance(artifacts, list) and artifacts else None
        if artifact is not None:
            found.append(
                {
                    "id": frame.id,
                    "label": frame.label,
                    "x": frame.x,
                    "y": frame.y,
                    "width": frame.width,
                    "height": frame.height,
                    "artifact": artifact,
                },
            )
    return found


def _board(row: Row) -> Board:
    """Read a published board from its row.

    Returns:
        The board.
    """
    frames = row["frames"]
    origin = row["origin"]
    return Board(
        id=str(row["id"]),
        title=str(row["title"]),
        namespace=str(row["namespace"]),
        frames=tuple(
            Frame(
                id=str(f["id"]),
                label=str(f["label"]),
                origin={},
                x=int(f["x"]),
                y=int(f["y"]),
                width=int(f["width"]),
                height=int(f["height"]),
                artifact_id=str(f["artifact_id"]),
            )
            for f in (frames if isinstance(frames, list) else [])
            if isinstance(f, dict)
        ),
        origin={str(k): str(v) for k, v in origin.items()} if isinstance(origin, dict) else {},
    )


def _frame_json(frame: Frame) -> dict[str, object]:
    return {
        "id": frame.id,
        "label": frame.label,
        "artifact_id": frame.artifact_id,
        "x": frame.x,
        "y": frame.y,
        "width": frame.width,
        "height": frame.height,
    }


def _board_json(board: Board) -> dict[str, object]:
    return {"id": board.id, "title": board.title, "namespace": board.namespace, "origin": dict(board.origin)}
