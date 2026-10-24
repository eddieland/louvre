"""The demo: published once, a part at a time, with the design study as its board."""

import re

import pytest

from louvre.core import accounts, demo, style
from louvre.core.boards import shown
from louvre.core.db import Connection
from louvre.core.decisions import Decisions
from louvre.core.store import Store
from louvre.core.style.check import check


def reader(conn: Connection) -> Store:
    """Read the demo, as a reader who has not signed in does.

    Returns:
        The store.
    """
    return Store(conn, accounts.reader_scope({demo.NAMESPACE}))


def test_the_demo_is_published_once(conn: Connection) -> None:
    assert demo.seed(conn) is True
    assert demo.seed(conn) is False

    listed = reader(conn).overview()["artifacts"]
    assert isinstance(listed, list)
    assert len(listed) == 9


def test_a_part_a_database_lacks_is_published_alone(conn: Connection) -> None:
    demo.seed(conn)
    conn.execute(
        "UPDATE artifacts SET deleted_at = now() WHERE origin @> %s::jsonb",
        ('{"canopy.ticket": "LOUVRE-M1"}',),
    )

    assert demo.seed(conn) is True

    titles = [a["title"] for a in reader(conn).overview()["artifacts"]]  # type: ignore[union-attr]
    assert sorted(t for t in titles if t.startswith("Direction")) == [
        "Direction: Gallery",
        "Direction: Margins",
        "Direction: Studio",
    ]
    assert len(titles) == 9


def test_the_design_study_is_a_board_of_each_direction_at_a_laptops_size_and_a_phones(conn: Connection) -> None:
    demo.seed(conn)

    frames = shown(reader(conn), [demo.BOARD], demo.BOARD.id)["frames"]

    assert isinstance(frames, list)
    assert [(f["id"], f["width"], f["height"], f["artifact"]["title"]) for f in frames] == [
        ("gallery-laptop", 1440, 900, "Direction: Gallery"),
        ("gallery-phone", 390, 844, "Direction: Gallery"),
        ("studio-laptop", 1440, 900, "Direction: Studio"),
        ("studio-phone", 390, 844, "Direction: Studio"),
        ("margins-laptop", 1440, 900, "Direction: Margins"),
        ("margins-phone", 390, 844, "Direction: Margins"),
    ]
    # A row a direction, its phone beside its laptop, no two frames overlapping.
    assert [(f["x"] > 0, f["y"] // 1000) for f in frames] == [
        (False, 0),
        (True, 0),
        (False, 1),
        (True, 1),
        (False, 2),
        (True, 2),
    ]
    boxes = [(f["x"], f["y"], f["x"] + f["width"], f["y"] + f["height"]) for f in frames]
    assert not [
        (a, b)
        for i, a in enumerate(boxes)
        for b in boxes[i + 1 :]
        if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
    ]


def test_the_studys_pages_load_nothing_from_the_network(conn: Connection) -> None:
    demo.seed(conn)
    store = reader(conn)

    for frame in shown(store, [demo.BOARD], demo.BOARD.id)["frames"]:  # type: ignore[union-attr]
        content = str(store.read(frame["artifact"]["id"])["content"])
        assert "https://" not in content, frame["id"]


@pytest.mark.parametrize(
    "origin",
    [
        {"canopy.report": "weekly"},
        {"canopy.ticket": "PAY-151"},
        {"canopy.ticket": "PAY-160"},
        {"canopy.ticket": "PAY-163"},
    ],
)
def test_its_house_style_pages_use_only_the_styles_classes_and_pass_its_check(
    conn: Connection,
    origin: dict[str, str],
) -> None:
    demo.seed(conn)
    store = reader(conn)
    [made] = store.overview(origin=origin)["artifacts"]  # type: ignore[misc]
    content = str(store.read(made["id"])["content"])
    classes = {name for names in re.findall(r'class="([^"]+)"', content) for name in names.split()}

    assert style.CSS.rstrip() in content
    assert classes - {"louvre"} <= set(re.findall(r"\.(l-[a-z0-9-]+)", style.CSS))
    assert check(content) == []


def test_its_decisions_are_asked_once_and_a_database_without_them_gets_them_alone(conn: Connection) -> None:
    demo.seed(conn)
    conn.execute("DELETE FROM decisions")

    assert demo.seed(conn) is True
    assert demo.seed(conn) is False

    found = Decisions(reader(conn)).listed()["decisions"]
    assert isinstance(found, list)
    assert [(d["question"], d["state"], [o["count"] for o in d["options"]]) for d in found] == [
        ("Ship these notes with Thursday's release?", "closed", [2, 0]),
        ("Which fix ships first?", "open", [2, 0, 0]),
    ]
    assert [(p["login"], p["answered"]) for p in found[1]["asked"]] == [("ana", False), ("raj", True)]
