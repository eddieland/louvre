"""A person's inbox: what is new to them on the artifacts they take part in, and reading it."""

import pytest

from louvre.core import accounts, inbox
from louvre.core.db import Connection
from louvre.core.store import Store
from louvre.core.text import Anchor
from tests.conftest import MakeAgent, person

#: A report with two passages to comment on.
REPORT = "<h1>Checkout</h1><p>We will retry the fraud check twice.</p><p>p95 rose to 1.2 s.</p>"


@pytest.fixture
def ana(conn: Connection) -> Store:
    """A store as Ana, signed in on the web."""
    return Store(conn, accounts.person_scope(person(conn, "ana", "Ana Ruiz")))


@pytest.fixture
def raj(conn: Connection) -> Store:
    """A store as Raj, signed in on the web."""
    return Store(conn, accounts.person_scope(person(conn, "raj", "Raj Patel")))


def publish(worker: Store) -> str:
    """Publish the report as Sam's agent.

    Returns:
        Its id.
    """
    return str(worker.publish(title="Checkout", content_type="text/html", content=REPORT)["artifact_id"])


def read_now(conn: Connection, account_id: str, artifact_id: str, version: int = 1) -> None:
    """Read an artifact's page as its person would: through the `seq` its threads were read at."""
    through, _ = inbox.unread(conn, account_id, artifact_id)
    inbox.read(conn, account_id, artifact_id, version=version, through=through)


def test_an_artifact_an_agent_published_is_new_to_its_person_alone(conn: Connection, agent: MakeAgent) -> None:
    artifact = publish(agent())
    person(conn, "ana")

    [entry] = inbox.inbox(conn, "dev:sam")

    assert entry["artifact"] == {
        "id": artifact,
        "title": "Checkout",
        "namespace": "canopy/sam",
        "origin": {},
        "latest_version": 1,
        "created_at": entry["artifact"]["created_at"],  # type: ignore[index]
    }
    assert (entry["read_version"], entry["unread"], entry["threads"], entry["news"]) == (None, 0, 0, [])
    assert inbox.inbox(conn, "dev:ana") == []
    read_now(conn, "dev:sam", artifact)
    assert inbox.inbox(conn, "dev:sam") == []


def test_a_reply_to_a_persons_comment_is_news_to_them_and_their_own_words_are_not(
    conn: Connection,
    agent: MakeAgent,
    ana: Store,
) -> None:
    worker = agent()
    artifact = publish(worker)
    read_now(conn, "dev:ana", artifact)
    thread = str(ana.comment(artifact, Anchor.of("retry the fraud check twice"), "Why twice?")["thread_id"])
    assert inbox.inbox(conn, "dev:ana") == []

    worker.reply(thread, "Once was not enough last quarter.")

    [entry] = inbox.inbox(conn, "dev:ana")
    assert (entry["read_version"], entry["unread"], entry["threads"]) == (1, 1, 1)
    [news] = entry["news"]  # type: ignore[misc]
    assert news["kind"] == "comment_created"
    assert news["thread_id"] == thread
    assert news["passage"] == "retry the fraud check twice"
    assert news["body"] == "Once was not enough last quarter."
    assert news["author"]["kind"] == "agent"
    assert news["author"]["on_behalf_of"] == "dev:sam"


def test_a_persons_own_agent_is_no_news_to_them_but_others_are(conn: Connection, agent: MakeAgent, ana: Store) -> None:
    worker = agent()
    artifact = publish(worker)
    read_now(conn, "dev:sam", artifact)

    thread = str(ana.comment(artifact, None, "Ship it?")["thread_id"])
    worker.reply(thread, "After review.")

    [entry] = inbox.inbox(conn, "dev:sam")
    assert [n["body"] for n in entry["news"]] == ["Ship it?"]  # type: ignore[attr-defined]


def test_resolving_and_reopening_are_news_and_the_newest_comes_first(
    conn: Connection,
    agent: MakeAgent,
    ana: Store,
    raj: Store,
) -> None:
    artifact = publish(agent())
    read_now(conn, "dev:ana", artifact)
    thread = str(ana.comment(artifact, Anchor.of("p95 rose"), "Every region?")["thread_id"])

    raj.reply(thread, "Every one.")
    raj.resolve(thread, resolved=True)
    raj.resolve(thread, resolved=False)
    raj.reply(thread, "Except ap-south.")

    [entry] = inbox.inbox(conn, "dev:ana")
    assert entry["unread"] == 4
    assert [n["kind"] for n in entry["news"]] == ["comment_created", "thread_reopened", "thread_resolved"]  # type: ignore[attr-defined]


def test_edits_and_deletions_are_not_news_and_a_deleted_comment_is_quoted_without_its_words(
    conn: Connection,
    agent: MakeAgent,
    ana: Store,
    raj: Store,
) -> None:
    artifact = publish(agent())
    read_now(conn, "dev:ana", artifact)
    thread = str(ana.comment(artifact, None, "Ready?")["thread_id"])
    comment = str(raj.reply(thread, "Yes.")["comment_id"])

    raj.edit(comment, "Yes, ship it.")
    raj.delete(comment)

    [entry] = inbox.inbox(conn, "dev:ana")
    assert entry["unread"] == 1
    assert entry["news"][0]["body"] is None  # type: ignore[index]


def test_a_comment_after_the_page_was_read_is_still_new(conn: Connection, agent: MakeAgent, ana: Store) -> None:
    worker = agent()
    artifact = publish(worker)
    thread = str(ana.comment(artifact, None, "Ready?")["thread_id"])
    through, _ = inbox.unread(conn, "dev:ana", artifact)

    worker.reply(thread, "Almost.")
    inbox.read(conn, "dev:ana", artifact, version=1, through=through)

    [entry] = inbox.inbox(conn, "dev:ana")
    assert entry["unread"] == 1
    assert inbox.unread(conn, "dev:ana", artifact)[1] == {thread}


def test_a_new_version_is_news_to_those_who_take_part(conn: Connection, agent: MakeAgent, ana: Store) -> None:
    worker = agent()
    artifact = publish(worker)
    ana.comment(artifact, None, "Shorter, please.")
    read_now(conn, "dev:ana", artifact)

    worker.publish(title="Checkout", content_type="text/html", content="<p>Shorter.</p>", artifact_id=artifact)

    [entry] = inbox.inbox(conn, "dev:ana")
    assert (entry["read_version"], entry["artifact"]["latest_version"], entry["unread"]) == (1, 2, 0)  # type: ignore[index]
    read_now(conn, "dev:ana", artifact, version=2)
    assert inbox.inbox(conn, "dev:ana") == []


def test_a_read_never_moves_back_or_past_what_the_artifact_has(conn: Connection, agent: MakeAgent, ana: Store) -> None:
    worker = agent()
    artifact = publish(worker)
    ana.comment(artifact, None, "Shorter, please.")
    worker.publish(title="Checkout", content_type="text/html", content="<p>Shorter.</p>", artifact_id=artifact)
    inbox.read(conn, "dev:ana", artifact, version=99, through=10**12)
    worker.publish(title="Checkout", content_type="text/html", content="<p>Short.</p>", artifact_id=artifact)
    worker.comment(artifact, None, "Shortened.")

    inbox.read(conn, "dev:ana", artifact, version=1, through=0)

    [entry] = inbox.inbox(conn, "dev:ana")
    assert (entry["read_version"], entry["unread"]) == (2, 1)


def test_reading_everything_empties_the_inbox_and_a_deleted_artifact_leaves_it(
    conn: Connection,
    agent: MakeAgent,
    ana: Store,
) -> None:
    worker = agent()
    first, second = publish(worker), publish(worker)
    for artifact in (first, second):
        worker.reply(str(ana.comment(artifact, None, "Ready?")["thread_id"]), "Yes.")
    assert len(inbox.inbox(conn, "dev:ana")) == 2

    sam = Store(conn, accounts.person_scope(person(conn, "sam", "Sam Okafor")))
    sam.delete_artifact(first)
    assert [e["artifact"]["id"] for e in inbox.inbox(conn, "dev:ana")] == [second]  # type: ignore[index]

    assert inbox.read_all(conn, "dev:ana") == 1
    assert inbox.inbox(conn, "dev:ana") == []


def test_threads_are_new_only_to_those_who_take_part(
    conn: Connection,
    agent: MakeAgent,
    ana: Store,
    raj: Store,
) -> None:
    artifact = publish(agent())
    thread = str(ana.comment(artifact, None, "Ready?")["thread_id"])
    read_now(conn, "dev:ana", artifact)
    raj.reply(thread, "Not yet.")

    assert inbox.unread(conn, "dev:ana", artifact)[1] == {thread}
    assert inbox.unread(conn, "dev:sam", artifact)[1] == {thread}
    person(conn, "kim")
    assert inbox.unread(conn, "dev:kim", artifact)[1] == set()
