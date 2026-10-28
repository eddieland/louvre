"""Search across artifacts: words found at a word's start, in titles, latest versions, and comments, and quoted."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from louvre.core import accounts, search
from louvre.core.db import Connection
from louvre.core.search import ELLIPSIS, Query
from louvre.core.store import Refused, Store
from louvre.core.text import Anchor
from tests.conftest import MakeAgent, person

#: A report, its words on more than one line, as a version's text holds them.
REPORT = (
    "<h1>Checkout latency</h1><p>We will retry the fraud check twice before declining a card.</p>"
    "<p>The p95 rose to 1.2 s after the cache was sharded.</p>"
)


@pytest.fixture
def ana(conn: Connection) -> Store:
    """A store as Ana, signed in on the web, who reads every namespace."""
    return Store(conn, accounts.person_scope(person(conn, "ana", "Ana Ruiz")))


def titles(listed: dict[str, object]) -> list[str]:
    """Name the artifacts a list holds, in its order.

    Returns:
        Their titles.
    """
    artifacts = listed["artifacts"]
    assert isinstance(artifacts, list)
    return [str(a["title"]) for a in artifacts]


def hits(runs: object) -> list[str]:
    """Pick the words a quote marks as found.

    Returns:
        Their text, in order.
    """
    assert isinstance(runs, list)
    return [str(r["text"]) for r in runs if r.get("hit")]


def text_of(runs: object) -> str:
    """Join a quote's runs.

    Returns:
        The quote's text.
    """
    assert isinstance(runs, list)
    return "".join(str(r["text"]) for r in runs)


def test_a_query_is_its_words_each_once_in_any_case() -> None:
    assert Query.of("  Retry  the retry\tFRAUD ").words == ("retry", "the", "fraud")
    assert Query.of("   ").words == ()


def test_a_word_is_found_at_a_words_start_in_any_case() -> None:
    query = Query.of("retr")

    assert hits(query.runs("Retry, retries, metric, and RETRACT.")) == ["Retr", "retr", "RETR"]


def test_the_longer_of_two_words_is_marked_where_both_are_found() -> None:
    assert hits(Query.of("fra fraud").runs("the fraud check")) == ["fraud"]


def test_a_title_with_nothing_found_is_one_run() -> None:
    assert Query.of("fraud").runs("Checkout") == [{"text": "Checkout"}]
    assert Query.of("fraud").runs("") == [{"text": ""}]


@given(st.text(max_size=80), st.lists(st.text(min_size=1, max_size=6), min_size=1, max_size=3))
def test_a_quotes_runs_are_its_text_whole(text: str, words: list[str]) -> None:
    query = Query(tuple(words))

    assert text_of(query.runs(text)) == text


def test_a_passage_is_quoted_around_its_words_on_one_line() -> None:
    text = "Checkout latency\n" + "word " * 40 + "We will retry the fraud check twice.\n" + "more " * 40

    [passage] = Query.of("fraud").passages(text)

    quoted = text_of(passage)
    assert quoted.startswith(ELLIPSIS)
    assert quoted.endswith(ELLIPSIS)
    assert "\n" not in quoted
    assert "We will retry the fraud check twice. more" in quoted
    assert hits(passage) == ["fraud"]


def test_passages_that_would_overlap_are_one_and_at_most_three_are_quoted() -> None:
    near = Query.of("fraud check").passages("the fraud check")
    far = Query.of("x").passages(" ".join(["x", "filler " * 30] * 5))

    assert [text_of(p) for p in near] == ["the fraud check"]
    assert len(far) == search.QUOTED


def test_a_comment_is_quoted_whole_when_it_is_short() -> None:
    assert text_of(Query.of("twice").excerpt("Why twice?")) == "Why twice?"


def test_an_artifact_is_found_by_its_title_its_latest_version_or_a_comment(ana: Store, agent: MakeAgent) -> None:
    sam = agent()
    sam.publish(title="Checkout latency", content_type="text/html", content=REPORT)
    sam.publish(title="Fraud rules", content_type="text/markdown", content="# Rules\n\nNothing about cards.")
    plan = str(sam.publish(title="Plan", content_type="text/markdown", content="# Plan\n\nShip it.")["artifact_id"])
    ana.comment(plan, Anchor.of("Ship it."), "Not before the fraud review.")
    sam.publish(title="Other", content_type="text/markdown", content="# Other\n\nUnrelated.")

    assert titles(ana.overview(query="fraud")) == ["Plan", "Fraud rules", "Checkout latency"]
    assert titles(ana.overview(query="FRAUD card")) == ["Fraud rules", "Checkout latency"]
    assert titles(ana.overview(query="fraud review")) == ["Plan"]
    assert titles(ana.overview(query="raud")) == []
    assert titles(ana.overview(query="  ")) == ["Other", "Plan", "Fraud rules", "Checkout latency"]


def test_a_found_artifact_says_where_its_words_are(ana: Store, agent: MakeAgent) -> None:
    sam = agent()
    report = str(sam.publish(title="Checkout latency", content_type="text/html", content=REPORT)["artifact_id"])
    thread = str(ana.comment(report, Anchor.of("retry the fraud check twice"), "Why retry twice?")["thread_id"])
    sam.reply(thread, "Once was not enough.")

    [artifact] = ana.overview(query="retry checkout")["artifacts"]  # type: ignore[misc]

    found = artifact["found"]
    assert hits(found["title"]) == ["Checkout"]
    [passage] = found["passages"]
    assert hits(passage) == ["Checkout", "retry"]
    assert text_of(passage).startswith("Checkout latency We will retry")
    [comment] = found["comments"]
    assert comment["thread_id"] == thread
    assert comment["author"] == {"id": "dev:ana", "display_name": "Ana Ruiz", "kind": "person", "on_behalf_of": None}
    assert hits(comment["body"]) == ["retry"]


def test_comments_holding_the_most_words_are_quoted_first_and_a_deleted_one_never(
    ana: Store,
    agent: MakeAgent,
) -> None:
    sam = agent()
    report = str(sam.publish(title="Checkout latency", content_type="text/html", content=REPORT)["artifact_id"])
    thread = str(ana.comment(report, None, "The cache again.")["thread_id"])
    sam.reply(thread, "The cache is sharded now.")
    deleted = str(ana.reply(thread, "Is the cache sharded by cart?")["comment_id"])
    ana.delete(deleted)

    [artifact] = ana.overview(query="cache sharded")["artifacts"]  # type: ignore[misc]

    assert [text_of(c["body"]) for c in artifact["found"]["comments"]] == [
        "The cache is sharded now.",
        "The cache again.",
    ]


def test_only_the_latest_version_is_searched(ana: Store, agent: MakeAgent) -> None:
    sam = agent()
    report = str(
        sam.publish(title="Report", content_type="text/markdown", content="# Report\n\nThe fraud check.")[
            "artifact_id"
        ],
    )
    sam.publish(title="Report", content_type="text/markdown", content="# Report\n\nThe risk check.", artifact_id=report)

    assert titles(ana.overview(query="fraud")) == []
    assert titles(ana.overview(query="risk")) == ["Report"]


def test_postgres_finds_what_python_quotes_for_words_a_pattern_would_misread(ana: Store, agent: MakeAgent) -> None:
    sam = agent()
    sam.publish(title="Notes", content_type="text/markdown", content="# Notes\n\nC++ costs $5 (a.b) [x] 1*2 a|b \\d")
    sam.publish(title="Decoy", content_type="text/markdown", content="# Decoy\n\nC costs 5 ab x 12 a b d")

    for word in ["c++", "$5", "(a.b)", "[x]", "1*2", "a|b", "\\d"]:
        [artifact] = ana.overview(query=word)["artifacts"]  # type: ignore[misc]
        assert artifact["title"] == "Notes", word
        [passage] = artifact["found"]["passages"]
        assert [h.casefold() for h in hits(passage)] == [word], word


def test_a_search_keeps_to_what_its_reader_reaches(conn: Connection, agent: MakeAgent) -> None:
    agent("canopy/sam").publish(title="Sam's fraud", content_type="text/markdown", content="# Fraud")
    agent("canopy/kim").publish(title="Kim's fraud", content_type="text/markdown", content="# Fraud")
    _, secret = accounts.mint(conn, person(conn, "kim"), "worker", "canopy/kim", {"read"})
    scope = accounts.token_scope(conn, secret)
    assert scope is not None

    assert titles(Store(conn, scope).overview(query="fraud")) == ["Kim's fraud"]


def test_a_search_is_held_to_its_bounds(ana: Store) -> None:
    with pytest.raises(Refused, match="at most 8 words"):
        ana.overview(query="a b c d e f g h i")
    with pytest.raises(Refused, match="query"):
        ana.overview(query="x" * (search.MAX_QUERY + 1))
