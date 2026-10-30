"""Presence: an agent's calls keep it present on the artifacts they name, and what it says it is doing lasts a while."""

from collections.abc import Callable
from datetime import timedelta

import pytest

from louvre.core import accounts
from louvre.core.db import Connection
from louvre.core.presence import MAX_NOTE, MOST_FOR, NOTED_EVERY, Activity, Presence, noted
from louvre.core.store import Code, Refused, Store
from louvre.core.text import Anchor
from tests.conftest import BASE_URL, MakeAgent, person

#: A page with a passage to comment on.
PAGE = "<h1>Checkout</h1><p>Batch the tax quote.</p>"


def refused(code: Code, call: Callable[[], object]) -> None:
    """Hold `call` to refusing with `code`."""
    with pytest.raises(Refused) as caught:
        call()
    assert caught.value.code == code


def reader(conn: Connection) -> Presence:
    """Presence as Ana reads it, signed in on the web.

    Returns:
        It.
    """
    return Presence(Store(conn, accounts.person_scope(person(conn, "ana", "Ana Lima")), base_url=BASE_URL))


def call(store: Store, do: Callable[[Store], object], completes: Activity | None = None) -> None:
    """Make one call through `store`, then note it, as the MCP server does with each tool call."""
    store.named.clear()
    do(store)
    noted(store, completes)


def aged(conn: Connection, by: timedelta) -> None:
    """Move every presence back in time by `by`, as if its calls had come that much earlier."""
    conn.execute(
        "UPDATE presence SET since = since - %(by)s, seen_at = seen_at - %(by)s, expires_at = expires_at - %(by)s",
        {"by": by},
    )


@pytest.fixture
def artifact(agent: MakeAgent) -> str:
    """The page, published by Sam's agent straight to the store, so nobody is present on it yet."""
    store = agent()
    made = store.publish(title="Checkout", content_type="text/html", content=PAGE)
    return str(made["artifact_id"])


def test_a_call_naming_an_artifact_makes_its_agent_present_there(
    conn: Connection,
    agent: MakeAgent,
    artifact: str,
) -> None:
    call(agent(), lambda s: s.read(artifact))

    [present] = reader(conn).present(artifact)

    assert present["author"] == {
        "id": "agent:dev:sam:canopy worker",
        "display_name": "canopy worker",
        "kind": "agent",
        "on_behalf_of": "dev:sam",
        "on_behalf_of_name": "Sam Okafor",
    }
    assert (present["activity"], present["note"], present["thread_id"]) == ("here", "", None)


def test_a_call_by_thread_names_the_threads_artifact(conn: Connection, agent: MakeAgent, artifact: str) -> None:
    store = agent()
    thread = str(store.comment(artifact, Anchor.of("Batch the tax quote."), "Measured?")["thread_id"])

    call(store, lambda s: s.resolve(thread, resolved=True))

    assert [p["activity"] for p in reader(conn).present(artifact)] == ["here"]


def test_a_list_or_a_feed_names_no_artifact(conn: Connection, agent: MakeAgent, artifact: str) -> None:
    call(agent(), lambda s: s.artifacts())
    call(agent(), lambda s: s.feed(None, 0, 10))

    assert reader(conn).present(artifact) == []


def test_a_person_reading_on_the_web_is_never_present(conn: Connection, artifact: str) -> None:
    ana = Store(conn, accounts.person_scope(person(conn, "ana", "Ana Lima")), base_url=BASE_URL)

    call(ana, lambda s: s.read(artifact))

    assert reader(conn).present(artifact) == []
    refused(Code.READ_ONLY, lambda: Presence(ana).say(artifact, Activity.READING))


def test_what_an_agent_says_it_is_doing_is_shown_with_its_note(
    conn: Connection,
    agent: MakeAgent,
    artifact: str,
) -> None:
    said = Presence(agent()).say(artifact, Activity.REVISING, note="Tightening the summary")

    assert (said["activity"], said["note"]) == ("revising", "Tightening the summary")
    [present] = reader(conn).present(artifact)
    assert (present["activity"], present["note"], present["expires_at"]) == (
        "revising",
        "Tightening the summary",
        said["expires_at"],
    )


def test_its_calls_keep_what_it_said_and_the_call_that_does_it_ends_it(
    conn: Connection,
    agent: MakeAgent,
    artifact: str,
) -> None:
    store = agent()
    Presence(store).say(artifact, Activity.REVISING, note="Tightening the summary")
    aged(conn, NOTED_EVERY)

    call(store, lambda s: s.read(artifact))
    assert [p["activity"] for p in reader(conn).present(artifact)] == ["revising"]

    call(
        store,
        lambda s: s.publish(title="Checkout", content_type="text/html", content=PAGE, artifact_id=artifact),
        Activity.REVISING,
    )
    [present] = reader(conn).present(artifact)
    assert (present["activity"], present["note"]) == ("here", "")


def test_replying_names_its_thread_and_a_comment_ends_it(conn: Connection, agent: MakeAgent, artifact: str) -> None:
    store = agent()
    thread = str(store.comment(artifact, Anchor.of("Batch the tax quote."), "Measured?")["thread_id"])

    Presence(store).say(artifact, Activity.REPLYING, thread_id=thread)
    assert [p["thread_id"] for p in reader(conn).present(artifact)] == [thread]

    call(store, lambda s: s.reply(thread, "Twice, under load."), Activity.REPLYING)
    assert [(p["activity"], p["thread_id"]) for p in reader(conn).present(artifact)] == [("here", None)]


def test_replying_needs_a_thread_on_the_artifact_and_only_replying_names_one(agent: MakeAgent, artifact: str) -> None:
    store = agent()
    other = str(store.publish(title="Other", content_type="text/html", content=PAGE)["artifact_id"])
    thread = str(store.comment(other, None, "On the other page.")["thread_id"])
    said = Presence(store)

    refused(Code.INVALID, lambda: said.say(artifact, Activity.REPLYING))
    refused(Code.INVALID, lambda: said.say(artifact, Activity.READING, thread_id=thread))
    refused(Code.NOT_FOUND, lambda: said.say(artifact, Activity.REPLYING, thread_id=thread))


def test_done_ends_its_presence_at_once(conn: Connection, agent: MakeAgent, artifact: str) -> None:
    store = agent()
    call(store, lambda s: s.read(artifact))

    assert Presence(store).say(artifact, None) == {"artifact_id": artifact, "activity": "done"}

    assert reader(conn).present(artifact) == []


def test_a_presence_past_its_expiry_is_gone_and_a_call_starts_it_afresh(
    conn: Connection,
    agent: MakeAgent,
    artifact: str,
) -> None:
    store = agent()
    Presence(store).say(artifact, Activity.REVISING, note="Tightening the summary")
    aged(conn, MOST_FOR)

    assert reader(conn).present(artifact) == []

    call(store, lambda s: s.read(artifact))
    [present] = reader(conn).present(artifact)
    assert (present["activity"], present["note"]) == ("here", "")
    assert present["since"] == present["seen_at"]


def test_a_call_is_noted_at_most_once_in_a_while(conn: Connection, agent: MakeAgent, artifact: str) -> None:
    store = agent()
    call(store, lambda s: s.read(artifact))
    [first] = reader(conn).present(artifact)

    call(store, lambda s: s.read(artifact))
    assert [p["seen_at"] for p in reader(conn).present(artifact)] == [first["seen_at"]]

    aged(conn, NOTED_EVERY)
    call(store, lambda s: s.read(artifact))
    [later] = reader(conn).present(artifact)
    assert str(later["seen_at"]) > str(first["seen_at"])


def test_a_call_keeps_a_short_activity_present_however_soon_it_comes(
    conn: Connection,
    agent: MakeAgent,
    artifact: str,
) -> None:
    store = agent()
    said = Presence(store).say(artifact, Activity.READING, lasting=timedelta(seconds=10))

    call(store, lambda s: s.read(artifact))

    [present] = reader(conn).present(artifact)
    assert present["activity"] == "reading"
    assert str(present["expires_at"]) > str(said["expires_at"])


def test_the_same_activity_said_again_keeps_when_it_started(conn: Connection, agent: MakeAgent, artifact: str) -> None:
    said = Presence(agent())
    said.say(artifact, Activity.READING)
    aged(conn, timedelta(minutes=1))
    [before] = reader(conn).present(artifact)

    said.say(artifact, Activity.READING, note="The threads now")
    assert [p["since"] for p in reader(conn).present(artifact)] == [before["since"]]

    said.say(artifact, Activity.REVISING)
    assert [p["since"] for p in reader(conn).present(artifact)] != [before["since"]]


def test_each_agent_is_present_apart_the_longest_at_it_first(conn: Connection, agent: MakeAgent, artifact: str) -> None:
    Presence(agent()).say(artifact, Activity.REVISING)
    aged(conn, timedelta(seconds=30))
    sam = person(conn, "sam", "Sam Okafor")
    _, secret = accounts.mint(conn, sam, "reviewer", "canopy/sam", {"read"})
    scope = accounts.token_scope(conn, secret)
    assert scope is not None

    Presence(Store(conn, scope, base_url=BASE_URL)).say(artifact, Activity.READING)

    present = reader(conn).present(artifact)
    assert [p["activity"] for p in present] == ["revising", "reading"]
    assert [p["author"] for p in present][1] == {
        "id": "agent:dev:sam:reviewer",
        "display_name": "reviewer",
        "kind": "agent",
        "on_behalf_of": "dev:sam",
        "on_behalf_of_name": "Sam Okafor",
    }


def test_an_artifact_outside_the_scope_is_refused(agent: MakeAgent, artifact: str) -> None:
    elsewhere = Presence(agent("canopy/kim"))

    refused(Code.OUT_OF_SCOPE, lambda: elsewhere.say(artifact, Activity.READING))
    refused(Code.OUT_OF_SCOPE, lambda: elsewhere.present(artifact))
    refused(Code.NOT_FOUND, lambda: elsewhere.say("a_missing", Activity.READING))


def test_a_note_and_a_time_are_held_to_their_bounds(agent: MakeAgent, artifact: str) -> None:
    said = Presence(agent())

    refused(Code.TOO_LONG, lambda: said.say(artifact, Activity.READING, note="x" * (MAX_NOTE + 1)))
    refused(Code.INVALID, lambda: said.say(artifact, Activity.READING, lasting=MOST_FOR + timedelta(seconds=1)))
    refused(Code.INVALID, lambda: said.say(artifact, Activity.READING, lasting=timedelta(seconds=1)))
