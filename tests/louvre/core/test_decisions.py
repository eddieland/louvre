import json
from collections.abc import Callable

import pytest

from louvre.core import accounts
from louvre.core.db import Connection
from louvre.core.decisions import MAX_OPTIONS, Decisions, Option
from louvre.core.geodata import Pick, PlaceKind
from louvre.core.store import Code, Refused, Store
from louvre.core.text import Anchor
from tests.conftest import BASE_URL, MakeAgent, person

#: A report with a passage for each fix it proposes.
REPORT = "<h1>Checkout</h1><p>Batch the tax quote.</p><p>Warm the pool.</p><p>Move the fraud check.</p>"
#: The options of the question asked on it: two on their passages, one on none.
OPTIONS = (
    Option("Batch the tax quote", "A day's work.", Anchor.of("Batch the tax quote.")),
    Option("Warm the pool", anchor=Anchor.of("Warm the pool.")),
    Option("Neither yet"),
)


def refused(code: Code, call: Callable[[], object]) -> None:
    with pytest.raises(Refused) as caught:
        call()
    assert caught.value.code == code


def as_person(conn: Connection, login: str, name: str) -> Decisions:
    """Decisions as a person signed in on the web.

    Returns:
        Them.
    """
    return Decisions(Store(conn, accounts.person_scope(person(conn, login, name)), base_url=BASE_URL))


@pytest.fixture
def sam_agent(agent: MakeAgent) -> Decisions:
    """Decisions as an agent of Sam's, in canopy/sam."""
    return Decisions(agent())


@pytest.fixture
def report(agent: MakeAgent) -> str:
    """The report, published by Sam's agent with an origin."""
    made = agent().publish(title="Checkout", content_type="text/html", content=REPORT, origin={"canopy.ticket": "P-1"})
    return str(made["artifact_id"])


@pytest.fixture
def asked(sam_agent: Decisions, report: str) -> str:
    """The question, asked of Ana and Raj, who has never signed in."""
    made = sam_agent.ask(report, "Which fix ships first?", OPTIONS, asked=["@Ana", "raj", "ana"])
    assert made["url"] == f"{BASE_URL}/a/{report}?decision={made['decision_id']}"
    return str(made["decision_id"])


def test_a_decision_reads_back_with_its_options_and_who_it_asks(
    sam_agent: Decisions,
    asked: str,
    report: str,
    conn: Connection,
) -> None:
    ana = as_person(conn, "ana", "Ana Ruiz")

    read = ana.read(asked)

    assert read["question"] == "Which fix ships first?"
    assert (read["artifact_id"], read["artifact_title"], read["version"], read["state"]) == (
        report,
        "Checkout",
        1,
        "open",
    )
    assert read["options"] == [
        {
            "id": "o1",
            "label": "Batch the tax quote",
            "detail": "A day's work.",
            "anchor": {"exact": "Batch the tax quote.", "prefix": "", "suffix": ""},
            "place": None,
            "count": 0,
        },
        {
            "id": "o2",
            "label": "Warm the pool",
            "detail": "",
            "anchor": {"exact": "Warm the pool.", "prefix": "", "suffix": ""},
            "place": None,
            "count": 0,
        },
        {"id": "o3", "label": "Neither yet", "detail": "", "anchor": None, "place": None, "count": 0},
    ]
    assert read["asked"] == [
        {"login": "ana", "name": "Ana Ruiz", "answered": False},
        {"login": "raj", "name": None, "answered": False},
    ]
    assert read["author"] == {
        "id": "agent:dev:sam:canopy worker",
        "display_name": "canopy worker",
        "kind": "agent",
        "on_behalf_of": "dev:sam",
    }
    assert (read["mine"], read["awaits_me"], read["may_close"]) == (None, True, False)
    assert (sam_agent.read(asked)["awaits_me"], sam_agent.read(asked)["may_close"]) == (False, True)


def test_a_person_answers_and_changes_their_answer_and_the_feed_keeps_both(
    sam_agent: Decisions,
    asked: str,
    conn: Connection,
) -> None:
    ana = as_person(conn, "ana", "Ana Ruiz")
    raj = as_person(conn, "raj", "Raj Patel")

    ana.answer(asked, ["o2"], "The pool is the cheaper win.")
    ana.answer(asked, ["o1"], " On reflection, batching. ")
    raj.answer(asked, ["o1"])
    read = ana.read(asked)

    assert [o["count"] for o in read["options"]] == [2, 0, 0]  # type: ignore[index, union-attr]
    assert read["mine"] == {"choices": ["o1"], "note": "On reflection, batching."}
    assert read["awaits_me"] is False
    assert [(a["name"], a["choices"], a["note"]) for a in read["answers"]] == [  # type: ignore[union-attr]
        ("Ana Ruiz", ["o1"], "On reflection, batching."),
        ("Raj Patel", ["o1"], ""),
    ]
    assert [p["answered"] for p in read["asked"]] == [True, True]  # type: ignore[union-attr]
    feed = sam_agent.feed()
    assert [(e["kind"], e.get("choices"), e.get("author", {}).get("display_name")) for e in feed] == [  # type: ignore[union-attr]
        ("decision_asked", [], "canopy worker"),
        ("decision_answered", ["o2"], "Ana Ruiz"),
        ("decision_answered", ["o1"], "Ana Ruiz"),
        ("decision_answered", ["o1"], "Raj Patel"),
        ("end", None, None),
    ]
    assert feed[-1] == {"kind": "end", "through": feed[-2]["seq"]}  # type: ignore[index]


def test_an_answer_chooses_what_the_decision_offers(
    asked: str,
    sam_agent: Decisions,
    report: str,
    conn: Connection,
) -> None:
    ana = as_person(conn, "ana", "Ana Ruiz")
    several = str(sam_agent.ask(report, "Which ship this week?", OPTIONS, multiple=True)["decision_id"])

    refused(Code.INVALID, lambda: ana.answer(asked, ["o1", "o2"]))
    refused(Code.INVALID, lambda: ana.answer(asked, []))
    refused(Code.INVALID, lambda: ana.answer(asked, ["o9"]))
    refused(Code.TOO_LONG, lambda: ana.answer(asked, ["o1"], "x" * 4001))
    ana.answer(several, ["o3", "o1", "o1"])
    assert ana.read(several)["mine"] == {"choices": ["o1", "o3"], "note": ""}


def test_only_a_person_on_the_web_answers(asked: str, sam_agent: Decisions, conn: Connection) -> None:
    anonymous = Decisions(Store(conn, accounts.reader_scope({"canopy/sam"})))

    refused(Code.READ_ONLY, lambda: sam_agent.answer(asked, ["o1"]))
    refused(Code.READ_ONLY, lambda: anonymous.answer(asked, ["o1"]))
    assert anonymous.read(asked)["awaits_me"] is False


def test_who_asked_or_the_person_they_act_for_closes_it_once(
    sam_agent: Decisions,
    asked: str,
    report: str,
    conn: Connection,
) -> None:
    ana = as_person(conn, "ana", "Ana Ruiz")
    sam = as_person(conn, "sam", "Sam Okafor")
    other = str(sam_agent.ask(report, "Ship it?", (Option("Yes"), Option("No")))["decision_id"])

    refused(Code.OUT_OF_SCOPE, lambda: ana.close(asked))
    refused(Code.INVALID, lambda: sam_agent.close(asked, "o9"))
    assert sam_agent.close(asked, "o1", "Batching ships Monday.")["state"] == "closed"
    assert sam.close(other)["state"] == "closed"

    read = ana.read(asked)
    assert (read["state"], read["outcome"], read["outcome_note"], read["may_close"]) == (
        "closed",
        "o1",
        "Batching ships Monday.",
        False,
    )
    assert read["closed_at"] is not None
    refused(Code.CLOSED, lambda: sam_agent.close(asked))
    refused(Code.CLOSED, lambda: ana.answer(asked, ["o2"]))
    closed = [e for e in sam_agent.feed() if e.get("kind") == "decision_closed"]  # type: ignore[union-attr]
    assert [(e["decision_id"], e["choices"], e["note"]) for e in closed] == [  # type: ignore[index]
        (asked, ["o1"], "Batching ships Monday."),
        (other, [], ""),
    ]


@pytest.mark.parametrize(
    ("code", "question", "options", "asked"),
    [
        (Code.INVALID, " ", OPTIONS, ()),
        (Code.TOO_LONG, "q" * 501, OPTIONS, ()),
        (Code.INVALID, "Which?", OPTIONS[:1], ()),
        (Code.TOO_LONG, "Which?", tuple(Option(f"Option {i}") for i in range(MAX_OPTIONS + 1)), ()),
        (Code.INVALID, "Which?", (Option("Same"), Option(" same ")), ()),
        (Code.INVALID, "Which?", (Option("A"), Option("  ")), ()),
        (Code.TOO_LONG, "Which?", (Option("A"), Option("B", "d" * 501)), ()),
        (Code.INVALID, "Which?", OPTIONS, ("two words",)),
        (Code.TOO_LONG, "Which?", OPTIONS, tuple(f"p{i}" for i in range(21))),
        (Code.ANCHOR_NOT_FOUND, "Which?", (Option("A", anchor=Anchor.of("Not in it.")), Option("B")), ()),
    ],
)
def test_a_question_is_held_to_its_bounds(
    sam_agent: Decisions,
    report: str,
    code: Code,
    question: str,
    options: tuple[Option, ...],
    asked: tuple[str, ...],
) -> None:
    refused(code, lambda: sam_agent.ask(report, question, options, asked=asked))


def test_a_token_asks_and_reads_within_its_namespace_and_scopes(asked: str, report: str, agent: MakeAgent) -> None:
    elsewhere = Decisions(agent("canopy/raj"))
    reader = Decisions(agent(scopes=("read",)))

    refused(Code.OUT_OF_SCOPE, lambda: elsewhere.read(asked))
    refused(Code.OUT_OF_SCOPE, lambda: elsewhere.ask(report, "Which?", OPTIONS))
    refused(Code.OUT_OF_SCOPE, lambda: elsewhere.listed(artifact_id=report))
    assert elsewhere.listed()["decisions"] == []
    assert [e["kind"] for e in elsewhere.feed()] == ["end"]  # type: ignore[index]
    refused(Code.READ_ONLY, lambda: reader.ask(report, "Which?", OPTIONS))
    refused(Code.READ_ONLY, lambda: reader.close(asked))
    assert reader.read(asked)["id"] == asked
    refused(Code.NOT_FOUND, lambda: reader.read("d_missing"))


def test_decisions_list_by_artifact_state_and_origin_with_what_awaits_the_reader(
    sam_agent: Decisions,
    asked: str,
    report: str,
    agent: MakeAgent,
    conn: Connection,
) -> None:
    other = str(agent().publish(title="Other", content_type="text/markdown", content="Ship it?")["artifact_id"])
    later = str(sam_agent.ask(other, "Ship it?", (Option("Yes"), Option("No")), asked=["ana"])["decision_id"])
    sam_agent.close(later)
    ana = as_person(conn, "ana", "Ana Ruiz")

    assert [d["id"] for d in ana.listed()["decisions"]] == [later, asked]  # type: ignore[index, union-attr]
    assert ana.listed()["awaiting"] == 1
    assert [d["id"] for d in ana.listed(artifact_id=report)["decisions"]] == [asked]  # type: ignore[index, union-attr]
    assert [d["id"] for d in ana.listed(state="closed")["decisions"]] == [later]  # type: ignore[index, union-attr]
    assert [d["id"] for d in ana.listed(origin={"canopy.ticket": "P-1"})["decisions"]] == [asked]  # type: ignore[index, union-attr]
    assert sam_agent.listed()["awaiting"] == 0


def test_the_catalogue_counts_open_decisions_and_those_awaiting_the_reader(
    asked: str,
    report: str,
    conn: Connection,
) -> None:
    ana = Store(conn, accounts.person_scope(person(conn, "ana", "Ana Ruiz")))
    raj = Store(conn, accounts.person_scope(person(conn, "raj", "Raj Patel")))

    def counts(store: Store) -> tuple[object, object]:
        [listed] = store.overview()["artifacts"]  # type: ignore[misc]
        return listed["open_decisions"], listed["awaiting"]

    assert counts(ana) == (1, 1)
    Decisions(ana).answer(asked, ["o1"])
    assert counts(ana) == (1, 0)
    assert counts(raj) == (1, 1)


def test_the_feed_pages_and_filters_like_the_comment_feed(
    sam_agent: Decisions,
    asked: str,
    report: str,
    agent: MakeAgent,
    conn: Connection,
) -> None:
    as_person(conn, "ana", "Ana Ruiz").answer(asked, ["o1"])
    other = str(agent().publish(title="Other", content_type="text/markdown", content="x")["artifact_id"])
    sam_agent.ask(other, "Ship it?", (Option("Yes"), Option("No")))

    first = sam_agent.feed(limit=2)
    rest = sam_agent.feed(since=int(str(first[-1]["through"])))  # type: ignore[index]
    filtered = sam_agent.feed(origin={"canopy.ticket": "P-1"})

    assert [e["kind"] for e in first] == ["decision_asked", "decision_answered", "end"]  # type: ignore[index]
    assert [e["kind"] for e in rest] == ["decision_asked", "end"]  # type: ignore[index]
    assert [e.get("artifact_id") for e in filtered[:-1]] == [report, report]  # type: ignore[union-attr]
    assert filtered[-1]["through"] == rest[-1]["through"]  # type: ignore[index]
    refused(Code.INVALID, lambda: sam_agent.feed(limit=0))
    refused(Code.INVALID, lambda: sam_agent.feed(since=-1))


def test_a_deleted_artifacts_decisions_are_gone(
    sam_agent: Decisions,
    asked: str,
    report: str,
    conn: Connection,
) -> None:
    sam = Store(conn, accounts.person_scope(person(conn, "sam", "Sam Okafor")))
    sam.delete_artifact(report)

    refused(Code.NOT_FOUND, lambda: sam_agent.read(asked))
    assert sam_agent.listed()["decisions"] == []
    assert [e["kind"] for e in sam_agent.feed()] == ["end"]  # type: ignore[index]


def test_two_accounts_with_one_login_are_each_asked_and_either_answering_counts_as_answered(
    asked: str,
    conn: Connection,
) -> None:
    signed_in = as_person(conn, "ana", "Ana Ruiz")
    other = Decisions(
        Store(conn, accounts.person_scope(accounts.upsert_account(conn, accounts.Account("gh:1", "Ana", "Ana R")))),
    )

    assert (signed_in.read(asked)["awaits_me"], other.read(asked)["awaits_me"]) == (True, True)
    other.answer(asked, ["o1"])
    assert signed_in.read(asked)["asked"][0] == {"login": "ana", "name": "Ana R", "answered": True}  # type: ignore[index]
    assert signed_in.read(asked)["awaits_me"] is True


def test_an_option_may_be_about_a_place_on_a_map_said_in_its_words(sam_agent: Decisions, agent: MakeAgent) -> None:
    feature = {"type": "Feature", "properties": {"name": "P-113"}, "geometry": {"type": "Point", "coordinates": [0, 0]}}
    poles = json.dumps({"type": "FeatureCollection", "features": [feature]})
    on_map = str(agent().publish(title="Poles", content_type="application/geo+json", content=poles)["artifact_id"])

    made = sam_agent.ask(
        on_map,
        "Where does the crew start?",
        (
            Option("The leaning pole", place=Pick(PlaceKind.FEATURE, "P-113")),
            Option("The corner", place=Pick(PlaceKind.POINT, coordinates=(0.001, 0.002))),
        ),
    )
    pole, corner = sam_agent.read(str(made["decision_id"]))["options"]  # type: ignore[misc]

    assert pole["anchor"] == {"exact": "P-113", "prefix": "", "suffix": ""}
    assert pole["place"] == {
        "kind": "feature",
        "layer": "data",
        "id": "P-113",
        "label": "P-113",
        "geometry": feature["geometry"],
    }
    assert corner["anchor"]["exact"] == "0.00200° N, 0.00100° E"
    assert corner["place"]["kind"] == "point"


def test_an_option_is_about_a_passage_or_a_place_its_map_has(sam_agent: Decisions, report: str) -> None:
    place = Pick(PlaceKind.FEATURE, "P-113")
    both = Option("Both", anchor=Anchor.of("Warm the pool."), place=place)

    refused(Code.INVALID, lambda: sam_agent.ask(report, "?", (both, Option("Neither"))))
    refused(Code.INVALID, lambda: sam_agent.ask(report, "?", (Option("On a page", place=place), Option("Neither"))))
