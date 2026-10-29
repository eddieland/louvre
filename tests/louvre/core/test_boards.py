"""Boards: an agent publishes one of its artifacts, and each frame finds its artifact through the reader's store."""

import pytest

from louvre.core import accounts
from louvre.core.boards import GAP, MAX_FRAMES, Board, Boards, Frame, Framed, listing, shown
from louvre.core.db import Connection
from louvre.core.store import Code, Refused, Store
from louvre.core.text import Anchor
from tests.conftest import MakeAgent

#: A page for a frame to show.
PAGE = "<h1>Direction</h1><p>Serif type, and generous space.</p>"
#: A board of two frames on one artifact, and one on an artifact nobody published.
BOARD = Board(
    id="study",
    title="Study",
    namespace="canopy/sam",
    frames=(
        Frame("a-laptop", "Laptop, 1440", {"direction": "a"}, 0, 0, 1440, 900),
        Frame("a-phone", "Phone, 390", {"direction": "a"}, 1600, 0, 390, 844),
        Frame("b-laptop", "Laptop, 1440", {"direction": "b"}, 0, 1060, 1440, 900),
    ),
)


@pytest.fixture
def published(agent: MakeAgent) -> str:
    """Direction a, published twice over by Sam's agent: the board shows the newer, with a thread open on it."""
    store = agent()
    store.publish(title="Old a", content_type="text/html", content=PAGE, origin={"direction": "a"})
    made = store.publish(title="Direction a", content_type="text/html", content=PAGE, origin={"direction": "a"})
    store.comment(str(made["artifact_id"]), Anchor.of("generous space"), "How generous?")
    return str(made["artifact_id"])


def test_a_board_shows_each_frame_it_finds_with_its_newest_artifact(agent: MakeAgent, published: str) -> None:
    found = shown(agent(), [BOARD], "study")

    assert found["board"] == {"id": "study", "title": "Study", "namespace": "canopy/sam", "origin": {}}
    frames = found["frames"]
    assert isinstance(frames, list)
    assert [(f["id"], f["label"], f["x"], f["y"], f["width"], f["height"]) for f in frames] == [
        ("a-laptop", "Laptop, 1440", 0, 0, 1440, 900),
        ("a-phone", "Phone, 390", 1600, 0, 390, 844),
    ]
    assert {f["artifact"]["id"] for f in frames} == {published}
    assert frames[0]["artifact"]["open_threads"] == 1


def test_the_list_counts_the_frames_found_and_their_artifacts_open_threads(agent: MakeAgent, published: str) -> None:
    empty = Board("empty", "Empty", "canopy/sam", (Frame("x", "Phone, 390", {"direction": "x"}, 0, 0, 390, 844),))

    listed = listing(agent(), [BOARD, empty])

    assert published
    assert listed == [
        {"id": "study", "title": "Study", "namespace": "canopy/sam", "origin": {}, "frames": 2, "open_threads": 1},
    ]


def test_a_reader_outside_the_boards_namespace_finds_no_frame(conn: Connection, published: str) -> None:
    outside = Store(conn, accounts.reader_scope({"demo"}))

    assert published
    assert listing(outside, [BOARD]) == []
    assert shown(outside, [BOARD], "study")["frames"] == []


def test_no_board_by_that_id_is_not_found(agent: MakeAgent) -> None:
    with pytest.raises(Refused) as caught:
        shown(agent(), [BOARD], "nowhere")

    assert caught.value.code == Code.NOT_FOUND


def test_a_published_board_lays_its_rows_out_each_under_the_tallest_of_the_one_before(
    agent: MakeAgent,
    published: str,
) -> None:
    sam = agent()
    other = str(sam.publish(title="Direction b", content_type="text/html", content=PAGE)["artifact_id"])

    made = Boards(sam).publish(
        title="Two directions",
        rows=[
            [Framed(published, "Laptop, 1440", 1440, 900), Framed(published, "Phone, 390", 390, 844)],
            [Framed(other, "Phone, 390", 390, 844)],
        ],
        origin={"canopy.ticket": "PAY-142"},
    )
    board = Boards(sam).find(str(made["board_id"]))
    found = shown(sam, [board] if board else [], str(made["board_id"]))

    assert made == {"board_id": made["board_id"], "frames": 3, "url": f"https://louvre.test/b/{made['board_id']}"}
    assert found["board"] == {
        "id": made["board_id"],
        "title": "Two directions",
        "namespace": "canopy/sam",
        "origin": {"canopy.ticket": "PAY-142"},
    }
    frames = found["frames"]
    assert isinstance(frames, list)
    assert [(f["id"], f["label"], f["x"], f["y"], f["width"], f["height"]) for f in frames] == [
        ("f1", "Laptop, 1440", 0, 0, 1440, 900),
        ("f2", "Phone, 390", 1440 + GAP, 0, 390, 844),
        ("f3", "Phone, 390", 0, 900 + GAP, 390, 844),
    ]
    assert [f["artifact"]["id"] for f in frames] == [published, published, other]
    assert frames[0]["artifact"]["open_threads"] == 1


def test_a_board_published_again_takes_its_new_title_and_frames_and_keeps_its_origin(
    agent: MakeAgent,
    published: str,
) -> None:
    sam = agent()
    boards = Boards(sam)
    first = boards.publish(title="Study", rows=[[Framed(published, "Phone, 390", 390, 844)]], origin={"k": "v"})
    board_id = str(first["board_id"])

    again = boards.publish(
        title="Study, revised",
        rows=[[Framed(published, "Laptop, 1440", 1440, 900), Framed(published, "Phone, 390", 390, 844)]],
        board_id=board_id,
    )
    board = boards.find(board_id)

    assert again["board_id"] == board_id
    assert board is not None
    assert (board.title, dict(board.origin), [f.label for f in board.frames]) == (
        "Study, revised",
        {"k": "v"},
        ["Laptop, 1440", "Phone, 390"],
    )
    assert [b.id for b in boards.listed()] == [board_id]


def test_the_newest_board_is_listed_first_and_a_reader_reaches_only_its_namespace_s(
    conn: Connection,
    agent: MakeAgent,
    published: str,
) -> None:
    sam = agent()
    older = Boards(sam).publish(title="Older", rows=[[Framed(published, "Phone, 390", 390, 844)]])
    newer = Boards(sam).publish(title="Newer", rows=[[Framed(published, "Phone, 390", 390, 844)]])
    outside = Store(conn, accounts.reader_scope({"demo"}))

    assert [b.id for b in Boards(sam).listed()] == [newer["board_id"], older["board_id"]]
    assert Boards(outside).listed() == []
    assert Boards(sam).find("b_nowhere") is None
    with pytest.raises(Refused) as caught:
        Boards(outside).find(str(newer["board_id"]))
    assert caught.value.code == Code.OUT_OF_SCOPE


def test_a_frame_whose_artifact_is_deleted_is_left_off_its_board(
    conn: Connection,
    agent: MakeAgent,
    published: str,
) -> None:
    sam = agent()
    other = str(sam.publish(title="Direction b", content_type="text/html", content=PAGE)["artifact_id"])
    made = Boards(sam).publish(
        title="Study",
        rows=[[Framed(published, "Phone, 390", 390, 844), Framed(other, "Phone, 390", 390, 844)]],
    )
    conn.execute("UPDATE artifacts SET deleted_at = now() WHERE id = %s", (other,))
    board = Boards(sam).find(str(made["board_id"]))
    assert board is not None

    frames = shown(sam, [board], board.id)["frames"]

    assert isinstance(frames, list)
    assert [f["artifact"]["id"] for f in frames] == [published]


@pytest.mark.parametrize(
    ("title", "rows", "code"),
    [
        (" ", [[("a", "Phone", 390, 844)]], Code.INVALID),
        ("Study", [], Code.INVALID),
        ("Study", [[("a", "Phone", 390, 844)], []], Code.INVALID),
        ("Study", [[("a", " ", 390, 844)]], Code.INVALID),
        ("Study", [[("a", "x" * 61, 390, 844)]], Code.TOO_LONG),
        ("Study", [[("a", "Phone", 100, 844)]], Code.INVALID),
        ("Study", [[("a", "Phone", 390, 9000)]], Code.INVALID),
        ("Study", [[("a", "Phone", 390, 844)] * (MAX_FRAMES + 1)], Code.TOO_LONG),
        ("Study", [[("a_nowhere", "Phone", 390, 844)]], Code.NOT_FOUND),
    ],
)
def test_a_board_out_of_bounds_is_refused(
    agent: MakeAgent,
    published: str,
    title: str,
    rows: list[list[tuple[str, str, int, int]]],
    code: Code,
) -> None:
    framed = [[Framed(published if a == "a" else a, label, w, h) for a, label, w, h in row] for row in rows]

    with pytest.raises(Refused) as caught:
        Boards(agent()).publish(title=title, rows=framed)

    assert caught.value.code == code


def test_a_board_is_of_its_namespace_s_artifacts_and_published_with_publish(
    agent: MakeAgent,
    published: str,
) -> None:
    elsewhere = agent("canopy/ana")
    reader = agent(scopes=("read",))
    board = Boards(agent()).publish(title="Study", rows=[[Framed(published, "Phone, 390", 390, 844)]])
    rows = [[Framed(published, "Phone, 390", 390, 844)]]

    with pytest.raises(Refused) as outside:
        Boards(elsewhere).publish(title="Study", rows=rows)
    with pytest.raises(Refused) as again:
        Boards(elsewhere).publish(title="Study", rows=rows, board_id=str(board["board_id"]))
    with pytest.raises(Refused) as read_only:
        Boards(reader).publish(title="Study", rows=rows)
    with pytest.raises(Refused) as unknown:
        Boards(agent()).publish(title="Study", rows=rows, board_id="b_nowhere")
    with pytest.raises(Refused) as origin:
        Boards(agent()).publish(title="Study", rows=rows, board_id=str(board["board_id"]), origin={"k": "v"})

    assert outside.value.code == Code.OUT_OF_SCOPE
    assert again.value.code == Code.OUT_OF_SCOPE
    assert read_only.value.code == Code.READ_ONLY
    assert unknown.value.code == Code.NOT_FOUND
    assert origin.value.code == Code.INVALID
