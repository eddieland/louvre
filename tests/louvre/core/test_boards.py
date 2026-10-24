"""Boards: each frame finds its artifact by origin, through the reader's store."""

import pytest

from louvre.core import accounts
from louvre.core.boards import Board, Frame, listing, shown
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

    assert found["board"] == {"id": "study", "title": "Study", "namespace": "canopy/sam"}
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
    assert listed == [{"id": "study", "title": "Study", "namespace": "canopy/sam", "frames": 2, "open_threads": 1}]


def test_a_reader_outside_the_boards_namespace_finds_no_frame(conn: Connection, published: str) -> None:
    outside = Store(conn, accounts.reader_scope({"demo"}))

    assert published
    assert listing(outside, [BOARD]) == []
    assert shown(outside, [BOARD], "study")["frames"] == []


def test_no_board_by_that_id_is_not_found(agent: MakeAgent) -> None:
    with pytest.raises(Refused) as caught:
        shown(agent(), [BOARD], "nowhere")

    assert caught.value.code == Code.NOT_FOUND
