"""The demo: published once, a part at a time, with the design studies as its boards."""

import re

import pytest

from louvre.core import accounts, demo, files, style
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


def everything(store: Store) -> list[dict[str, object]]:
    """List every artifact the store reaches, a page at a time.

    Returns:
        The artifacts, newest first.
    """
    listed: list[dict[str, object]] = []
    cursor: str | None = None
    while True:
        page = store.overview(cursor=cursor)
        listed += page["artifacts"]  # type: ignore[arg-type]
        if page["next_cursor"] is None:
            return listed
        cursor = str(page["next_cursor"])


def test_the_demo_is_published_once(conn: Connection) -> None:
    assert demo.seed(conn) is True
    assert demo.seed(conn) is False

    assert len(everything(reader(conn))) == 55


def test_a_part_a_database_lacks_is_published_alone(conn: Connection) -> None:
    demo.seed(conn)
    conn.execute(
        "UPDATE artifacts SET deleted_at = now() WHERE origin @> %s::jsonb",
        ('{"canopy.ticket": "LOUVRE-M1"}',),
    )

    assert demo.seed(conn) is True

    titles = [str(a["title"]) for a in everything(reader(conn))]
    assert sorted(t for t in titles if t.startswith("Direction:")) == [
        "Direction: Gallery",
        "Direction: Margins",
        "Direction: Studio",
    ]
    assert len(titles) == 55


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


def test_canopys_style_study_is_a_board_of_its_looks_at_a_laptops_size_a_row_a_round(conn: Connection) -> None:
    demo.seed(conn)

    frames = shown(reader(conn), demo.BOARDS, demo.CANOPY_STYLE_BOARD.id)["frames"]

    assert isinstance(frames, list)
    assert [(f["id"], f["artifact"]["title"]) for f in frames] == [
        ("0-today-instrument-panel", "Today: instrument panel (canopy's style study)"),
        ("a-terminal-ledger", "Terminal ledger (canopy's style study)"),
        ("b-field-notes", "Field notes (canopy's style study)"),
        ("c-control-room", "Control room (canopy's style study)"),
        ("d-calm-inbox", "Calm inbox (canopy's style study)"),
        ("e-ops-inbox-dark", "Ops inbox (canopy's style study)"),
        ("e-ops-inbox-light", "Ops inbox, light (canopy's style study)"),
        ("f-ledger-inbox-dark", "Ledger inbox (canopy's style study)"),
        ("f-ledger-inbox-light", "Ledger inbox, light (canopy's style study)"),
    ]
    assert {(f["width"], f["height"]) for f in frames} == {(1440, 900)}
    assert [(f["x"] // 1440, f["y"] // 900) for f in frames] == [(c, 0) for c in range(5)] + [(c, 1) for c in range(4)]


def test_canopys_structure_study_is_a_board_of_its_screens_a_row_a_direction(conn: Connection) -> None:
    demo.seed(conn)
    store = reader(conn)

    frames = shown(store, demo.BOARDS, demo.CANOPY_STRUCTURE_BOARD.id)["frames"]

    assert isinstance(frames, list)
    rows: dict[int, list[str]] = {}
    for f in frames:
        rows.setdefault(f["y"], []).append(f["id"])
    assert [r[0] for r in rows.values()] == ["today", "d1", "d2", "d3", "d4", "compare", "r4", "r4-today-inbox"]
    assert [len(r) for r in rows.values()] == [6, 4, 4, 4, 4, 1, 9, 8]
    assert {(f["width"], f["height"]) for f in frames} == {(1440, 900)}
    by_id = {f["id"]: f["artifact"] for f in frames}
    assert by_id["d2"]["title"] == "Direction 2: Mailroom (canopy's structure study)"
    # Round four's first screens, as drawn, are round three's Mailroom, shown again.
    assert by_id["r4-inbox"]["id"] == by_id["d2-inbox"]["id"]
    assert len(store.overview(origin=demo.CANOPY_STRUCTURE_ORIGIN)["artifacts"]) == 37  # type: ignore[arg-type]


def test_each_screenshot_of_canopys_structure_study_is_beside_the_page_that_shows_it(conn: Connection) -> None:
    demo.seed(conn)
    store = reader(conn)
    pages = store.overview(origin=demo.CANOPY_STRUCTURE_ORIGIN)["artifacts"]
    assert isinstance(pages, list)

    shown_files = {}
    for page in pages:
        named = re.findall(r'<img src="([^"]+)"', str(store.read(page["id"])["content"]))
        listed = [f["path"] for f in files.listed(conn, page["id"], 1)]
        assert listed == named, page["title"]
        shown_files.update(dict.fromkeys(named, page["origin"]["page"]))

    assert shown_files == {f"{page}.png": page for page in demo.CANOPY_STRUCTURE_ROWS[0][1:]}


def test_the_studies_pages_load_nothing_from_the_network(conn: Connection) -> None:
    demo.seed(conn)
    store = reader(conn)
    studies = ({"canopy.ticket": "LOUVRE-M1"}, demo.CANOPY_STYLE_ORIGIN, demo.CANOPY_STRUCTURE_ORIGIN)
    pages = [a for origin in studies for a in store.overview(origin=origin)["artifacts"]]  # type: ignore[union-attr]

    assert len(pages) == 49
    for page in pages:
        content = str(store.read(page["id"])["content"])
        assert "https://" not in content, page["title"]


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
