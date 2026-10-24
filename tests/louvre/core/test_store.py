import json
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import psycopg
import pytest
from psycopg.sql import SQL

from louvre.core import accounts, db
from louvre.core.db import Connection
from louvre.core.geodata import Pick, PlaceKind
from louvre.core.store import Code, Refused, Scope, Store, Via
from louvre.core.text import Anchor
from tests.conftest import BASE_URL, MakeAgent, person

#: A report with a passage a thread anchors on, and a second version that rewords it.
V1 = "<h1>Checkout</h1><p>We will retry the fraud check twice before declining.</p><p>p95 rose to 1.2 s.</p>"
V2 = "<h1>Checkout</h1><p>We will retry the fraud check once.</p><p>p95 rose to 1.2 s.</p>"


@pytest.fixture
def ana(conn: Connection) -> Store:
    """A store as Ana, signed in on the web."""
    return Store(conn, accounts.person_scope(person(conn, "ana", "Ana Ruiz")))


def refused(code: Code, call: Callable[[], object]) -> None:
    with pytest.raises(Refused) as caught:
        call()
    assert caught.value.code == code


def test_publishing_makes_an_artifact_and_a_version_adds_to_it(agent: MakeAgent) -> None:
    store = agent()

    made = store.publish(title="Report", content_type="text/html", content=V1, origin={"canopy.ticket": "PAY-1"})
    again = store.publish(
        title="Report, v2",
        content_type="text/html",
        content=V2,
        artifact_id=str(made["artifact_id"]),
    )

    assert made["version"] == 1
    assert again == {"artifact_id": made["artifact_id"], "version": 2, "url": again["url"]}
    assert again["url"] == f"https://louvre.test/a/{made['artifact_id']}?v=2"
    latest = store.read(str(made["artifact_id"]))
    first = store.read(str(made["artifact_id"]), 1)
    assert latest["artifact"] == {
        "id": made["artifact_id"],
        "title": "Report, v2",
        "namespace": "canopy/sam",
        "origin": {"canopy.ticket": "PAY-1"},
        "latest_version": 2,
        "created_at": latest["artifact"]["created_at"],  # type: ignore[index]
    }
    assert first["content"] == V1
    assert first["text"] == "Checkout We will retry the fraud check twice before declining. p95 rose to 1.2 s."


def test_an_origin_is_set_once(agent: MakeAgent) -> None:
    store = agent()
    made = store.publish(title="R", content_type="text/html", content=V1)

    refused(
        Code.INVALID,
        lambda: store.publish(
            title="R",
            content_type="text/html",
            content=V2,
            artifact_id=str(made["artifact_id"]),
            origin={"a": "b"},
        ),
    )
    refused(
        Code.TOO_LONG,
        lambda: store.publish(title="R", content_type="text/html", content=V1, origin={str(i): "x" for i in range(17)}),
    )
    refused(Code.INVALID, lambda: store.publish(title="  ", content_type="text/html", content=V1))


def test_a_reworded_passage_is_gone_from_the_new_version_and_found_in_the_old(agent: MakeAgent, ana: Store) -> None:
    worker = agent()
    artifact = str(worker.publish(title="R", content_type="text/html", content=V1)["artifact_id"])
    thread = ana.comment(artifact, Anchor.of("retry the fraud check twice", "We will ", " before"), "Two doubles it.")
    worker.publish(title="R", content_type="text/html", content=V2, artifact_id=artifact)

    latest = ana.threads(artifact)
    first = ana.threads(artifact, version=1)

    assert latest["version"] == 2
    [gone] = latest["threads"]  # type: ignore[misc]
    assert gone["id"] == thread["thread_id"]
    assert gone["anchor_status"] == "passage_gone"
    assert gone["anchored_version"] == 1
    assert first["threads"][0]["anchor_status"] == "found"  # type: ignore[index]
    refused(Code.ANCHOR_NOT_FOUND, lambda: ana.comment(artifact, Anchor.of("twice before"), "Gone already."))


def test_a_comparison_says_what_changed_and_what_became_of_each_threads_passage(agent: MakeAgent, ana: Store) -> None:
    worker = agent()
    artifact = str(worker.publish(title="R", content_type="text/html", content=V1)["artifact_id"])
    reworded = ana.comment(artifact, Anchor.of("retry the fraud check twice"), "Two doubles it.")
    across = ana.comment(artifact, Anchor.of("We will retry the fraud check"), "Which check?")
    kept = ana.comment(artifact, Anchor.of("p95 rose to 1.2 s."), "Since when?")
    page = ana.comment(artifact, None, "Overall, good.")
    ana.resolve(str(page["thread_id"]), resolved=True)
    worker.publish(title="R", content_type="text/html", content=V2, artifact_id=artifact)
    later = ana.comment(artifact, Anchor.of("once"), "Better.")

    compared = ana.compare(artifact, 1)

    assert compared == {
        "artifact_id": artifact,
        "base": 1,
        "head": 2,
        "changes": [
            {
                "kind": "changed",
                "anchor": {
                    "exact": "once.",
                    "prefix": "t We will retry the fraud check",
                    "suffix": "p95 rose to 1.2 s.",
                },
                "added": "once.",
                "removed": "twice before declining.",
            },
        ],
        "words_added": 1,
        "words_removed": 3,
        # The thread opened on version 2 is no news of what changed since version 1.
        "threads": [
            {"thread_id": reworded["thread_id"], "state": "open", "outcome": "passage_gone"},
            {"thread_id": across["thread_id"], "state": "open", "outcome": "near_change"},
            {"thread_id": kept["thread_id"], "state": "open", "outcome": "near_change"},
            {"thread_id": page["thread_id"], "state": "resolved", "outcome": None},
        ],
    }
    assert later["thread_id"] not in [t["thread_id"] for t in compared["threads"]]  # type: ignore[union-attr]


def test_a_thread_is_near_a_change_within_its_anchors_context_of_it(agent: MakeAgent, ana: Store) -> None:
    worker = agent()
    first = "<p>Batch the tax quote into one call per cart.</p><p>Warm the pool at deploy.</p><p>Cache it for 60 s.</p>"
    second = first.replace("60 s", "five minutes")
    artifact = str(worker.publish(title="R", content_type="text/html", content=first)["artifact_id"])
    far = ana.comment(artifact, Anchor.of("Batch the tax quote"), "A day's work?")
    near = ana.comment(artifact, Anchor.of("Warm the pool at deploy."), "How long does it take?")
    worker.publish(title="R", content_type="text/html", content=second, artifact_id=artifact)

    assert ana.compare(artifact, 1)["threads"] == [
        {"thread_id": far["thread_id"], "state": "open", "outcome": "unchanged"},
        {"thread_id": near["thread_id"], "state": "open", "outcome": "near_change"},
    ]


def test_a_thread_whose_passage_left_before_the_earlier_version_is_no_news(agent: MakeAgent, ana: Store) -> None:
    worker = agent()
    artifact = str(worker.publish(title="R", content_type="text/html", content=V1)["artifact_id"])
    ana.comment(artifact, Anchor.of("twice before declining."), "Why twice?")
    worker.publish(title="R", content_type="text/html", content=V2, artifact_id=artifact)
    worker.publish(title="R", content_type="text/html", content=V2 + "<p>Ship it.</p>", artifact_id=artifact)

    assert ana.compare(artifact, 2)["threads"] == []
    assert [t["outcome"] for t in ana.compare(artifact, 1)["threads"]] == ["passage_gone"]  # type: ignore[union-attr]


def test_a_comparison_is_held_to_the_scope_and_to_versions_in_order(agent: MakeAgent, ana: Store) -> None:
    worker = agent()
    artifact = str(worker.publish(title="R", content_type="text/html", content=V1)["artifact_id"])
    worker.publish(title="R", content_type="text/html", content=V2, artifact_id=artifact)

    refused(Code.INVALID, lambda: ana.compare(artifact, 2))
    refused(Code.INVALID, lambda: ana.compare(artifact, 2, 1))
    refused(Code.INVALID, lambda: ana.compare(artifact, 0))
    refused(Code.NOT_FOUND, lambda: ana.compare(artifact, 1, 3))
    refused(Code.NOT_FOUND, lambda: ana.compare("a_none", 1))
    refused(Code.OUT_OF_SCOPE, lambda: agent("canopy/other").compare(artifact, 1))
    assert worker.compare(artifact, 1, 2)["head"] == 2


def test_a_thread_on_the_whole_artifact_has_no_anchor(agent: MakeAgent, ana: Store) -> None:
    artifact = str(agent().publish(title="R", content_type="text/html", content=V1)["artifact_id"])

    ana.comment(artifact, None, "Overall, good.")

    [thread] = ana.threads(artifact)["threads"]  # type: ignore[misc]
    assert thread["anchor"] is None
    assert thread["anchor_status"] is None


def test_comments_say_who_wrote_them_and_how(agent: MakeAgent, ana: Store) -> None:
    worker = agent()
    artifact = str(worker.publish(title="R", content_type="text/html", content=V1)["artifact_id"])
    thread = str(ana.comment(artifact, Anchor.of("p95 rose"), "Every region?")["thread_id"])
    worker.reply(thread, "Every region.")

    [listed] = ana.threads(artifact)["threads"]  # type: ignore[misc]

    person_said, agent_said = listed["comments"]
    assert person_said["author"] == {
        "id": "dev:ana",
        "display_name": "Ana Ruiz",
        "kind": "person",
        "on_behalf_of": None,
    }
    assert person_said["via"] == Via.WEB
    assert agent_said["author"] == {
        "id": "agent:dev:sam:canopy worker",
        "display_name": "canopy worker",
        "kind": "agent",
        "on_behalf_of": "dev:sam",
    }
    assert agent_said["via"] == Via.MCP


def test_the_feed_pages_by_cursor_and_misses_nothing(agent: MakeAgent, ana: Store) -> None:
    worker = agent()
    artifact = str(worker.publish(title="R", content_type="text/html", content=V1)["artifact_id"])
    threads = [str(ana.comment(artifact, Anchor.of("Checkout"), f"Comment {i}")["thread_id"]) for i in range(5)]
    worker.resolve(threads[0], resolved=True)
    worker.resolve(threads[0], resolved=True)

    seen: list[int] = []
    since = 0
    while True:
        page = worker.feed(since=since, limit=2)
        end = page[-1]
        assert end["kind"] == "end"
        seen.extend(int(str(change["seq"])) for change in page[:-1])
        if len(page) - 1 < 2:
            break
        since = int(str(end["through"]))

    assert seen == [1, 2, 3, 4, 5, 6]
    assert worker.feed(since=6) == [{"kind": "end", "through": 6}]
    refused(Code.INVALID, lambda: worker.feed(limit=201))


def test_the_feed_filters_by_origin_and_reads_through_what_it_leaves_out(agent: MakeAgent, ana: Store) -> None:
    worker = agent()
    one = str(worker.publish(title="R", content_type="text/html", content=V1, origin={"t": "1"})["artifact_id"])
    two = str(worker.publish(title="R", content_type="text/html", content=V1, origin={"t": "2"})["artifact_id"])
    ana.comment(one, None, "On one.")
    ana.comment(two, None, "On two.")

    page = worker.feed(origin={"t": "1"})

    assert [c["body"] for c in page[:-1]] == ["On one."]
    assert page[-1] == {"kind": "end", "through": 2}


def test_a_deleted_comment_is_empty_in_every_change(agent: MakeAgent, ana: Store) -> None:
    artifact = str(agent().publish(title="R", content_type="text/html", content=V1)["artifact_id"])
    made = ana.comment(artifact, None, "Oops.")
    ana.edit(str(made["comment_id"]), "Oops, edited.")
    ana.delete(str(made["comment_id"]))

    page = ana.feed()

    assert [c["kind"] for c in page[:-1]] == ["comment_created", "comment_edited", "comment_deleted"]
    assert {c["body"] for c in page[:-1]} == {""}
    refused(Code.NOT_FOUND, lambda: ana.edit(str(made["comment_id"]), "Back?"))


def test_only_the_author_edits_or_deletes_a_comment(agent: MakeAgent, ana: Store, conn: Connection) -> None:
    artifact = str(agent().publish(title="R", content_type="text/html", content=V1)["artifact_id"])
    made = ana.comment(artifact, None, "Mine.")
    raj = Store(conn, accounts.person_scope(person(conn, "raj")))

    refused(Code.OUT_OF_SCOPE, lambda: raj.edit(str(made["comment_id"]), "Not mine."))
    refused(Code.OUT_OF_SCOPE, lambda: raj.delete(str(made["comment_id"])))


def test_a_token_reaches_its_namespace_alone(agent: MakeAgent, ana: Store) -> None:
    sams = agent("canopy/sam")
    artifact = str(sams.publish(title="R", content_type="text/html", content=V1)["artifact_id"])
    others = agent("canopy/other")

    refused(Code.OUT_OF_SCOPE, lambda: others.read(artifact))
    refused(Code.OUT_OF_SCOPE, lambda: others.comment(artifact, None, "Hi."))
    assert others.artifacts() == {"artifacts": [], "next_cursor": None}
    assert others.feed() == [{"kind": "end", "through": 0}]
    assert [a["id"] for a in ana.artifacts()["artifacts"]] == [artifact]  # type: ignore[union-attr]


def test_a_tokens_scopes_hold_it(agent: MakeAgent) -> None:
    artifact = str(agent().publish(title="R", content_type="text/html", content=V1)["artifact_id"])
    reader = agent(scopes=("read",))
    writer = agent(scopes=("publish",))

    refused(Code.READ_ONLY, lambda: reader.publish(title="R", content_type="text/html", content=V1))
    refused(Code.READ_ONLY, lambda: reader.comment(artifact, None, "Hi."))
    refused(Code.OUT_OF_SCOPE, lambda: writer.read(artifact))
    assert writer.publish(title="R", content_type="text/html", content=V1)["version"] == 1


def test_a_person_comments_but_does_not_publish(ana: Store) -> None:
    refused(Code.READ_ONLY, lambda: ana.publish(title="R", content_type="text/html", content=V1))


def test_only_its_owner_deletes_an_artifact_and_then_it_is_gone(agent: MakeAgent, conn: Connection) -> None:
    worker = agent()
    artifact = str(worker.publish(title="R", content_type="text/html", content=V1)["artifact_id"])
    sam = Store(conn, accounts.person_scope(person(conn, "sam", "Sam Okafor")))
    ana = Store(conn, accounts.person_scope(person(conn, "ana")))

    refused(Code.READ_ONLY, lambda: worker.delete_artifact(artifact))
    refused(Code.OUT_OF_SCOPE, lambda: ana.delete_artifact(artifact))
    sam.delete_artifact(artifact)

    refused(Code.NOT_FOUND, lambda: ana.read(artifact))
    assert ana.artifacts()["artifacts"] == []


def test_a_list_pages_newest_first_with_what_the_web_shows(agent: MakeAgent, ana: Store) -> None:
    worker = agent()
    made = [str(worker.publish(title=f"R{i}", content_type="text/html", content=V1)["artifact_id"]) for i in range(3)]
    ana.comment(made[2], None, "Open.")

    listed = ana.overview()

    assert [a["id"] for a in listed["artifacts"]] == made[::-1]  # type: ignore[union-attr]
    assert [a["open_threads"] for a in listed["artifacts"]] == [1, 0, 0]  # type: ignore[union-attr]
    refused(Code.INVALID, lambda: ana.artifacts(cursor="nope"))


def test_a_markdown_version_is_shown_rendered(agent: MakeAgent, ana: Store) -> None:
    worker = agent()
    artifact = str(
        worker.publish(title="Notes", content_type="text/markdown", content="# Notes\n\nShort.")["artifact_id"],
    )

    assert ana.read(artifact)["text"] == "Notes Short."
    assert "<h1>Notes</h1>" in ana.page(artifact, 1)
    assert [v["n"] for v in ana.versions(artifact)["versions"]] == [1]  # type: ignore[union-attr]


def test_a_publish_waits_on_no_write_in_progress_but_a_change_waits_its_turn(
    agent: MakeAgent,
    ana: Store,
    database_url: str,
) -> None:
    store = agent()
    made = store.publish(title="Report", content_type="text/html", content=V1)
    thread = str(ana.comment(str(made["artifact_id"]), None, "First.")["thread_id"])

    with ana.writing(), elsewhere(database_url, store.scope) as other:
        ana.reply(thread, "Still writing.")
        published = other.publish(title="Other", content_type="text/html", content=V2)
        again = other.publish(
            title="Report",
            content_type="text/html",
            content=V2,
            artifact_id=str(made["artifact_id"]),
        )
        with pytest.raises(psycopg.errors.LockNotAvailable):
            other.comment(str(published["artifact_id"]), None, "In order.")

    assert (published["version"], again["version"]) == (1, 2)


def test_versions_published_at_once_take_the_next_numbers_in_turn(agent: MakeAgent, database_url: str) -> None:
    store = agent()
    made = str(store.publish(title="Report", content_type="text/html", content=V1)["artifact_id"])
    later: list[dict[str, object]] = []

    with elsewhere(database_url, store.scope, wait="10s") as other:
        waiting = threading.Thread(
            target=lambda: later.append(
                other.publish(title="R", content_type="text/html", content=V1, artifact_id=made),
            ),
        )
        with store.writing():
            store.publish(title="Report", content_type="text/html", content=V2, artifact_id=made)
            waiting.start()
            waiting.join(0.5)
            assert waiting.is_alive(), "the second publish should wait for the first's row"
        waiting.join()

    assert [v["n"] for v in store.versions(made)["versions"]] == [1, 2, 3]  # type: ignore[index, union-attr]
    assert later[0]["version"] == 3


def test_a_row_locked_to_change_holds_up_no_write_taking_a_seq(
    agent: MakeAgent,
    ana: Store,
    database_url: str,
    conn: Connection,
) -> None:
    store = agent()
    made = store.publish(title="Report", content_type="text/html", content=V1)
    thread = str(ana.comment(str(made["artifact_id"]), None, "First.")["thread_id"])

    # As resolving it holds the thread's row: a reply's change still checks its key against the row, and must not wait.
    with ana.writing(), elsewhere(database_url, store.scope) as other:
        conn.execute("SELECT id FROM threads WHERE id = %s FOR NO KEY UPDATE", (thread,))
        replied = other.reply(thread, "Not held up.")

    assert int(str(replied["seq"])) > 0


@contextmanager
def elsewhere(database_url: str, scope: Scope, *, wait: str = "1s") -> Iterator[Store]:
    """Open a store as `scope` on a connection of its own, as another request's, waiting at most `wait` on a lock."""
    with db.connect(database_url) as other:
        other.execute(SQL("SET lock_timeout = {}").format(wait))
        yield Store(other, scope, base_url=BASE_URL)


def test_a_thread_on_a_feature_is_gone_with_it_and_one_on_a_point_stays(agent: MakeAgent, ana: Store) -> None:
    def poles(*names: str) -> str:
        features = [
            {"type": "Feature", "id": f"pole-{n[2:]}", "properties": {"name": n}, "geometry": None} for n in names
        ]
        return json.dumps({"type": "FeatureCollection", "features": features})

    sam = agent()
    made = sam.publish(title="Poles", content_type="application/geo+json", content=poles("P-101", "P-102"))
    artifact = str(made["artifact_id"])
    on_feature = ana.comment(artifact, None, "Lamp out?", pick=Pick(PlaceKind.FEATURE, "pole-102"))
    on_point = ana.comment(
        artifact,
        None,
        "A pole is missing here.",
        pick=Pick(PlaceKind.POINT, coordinates=(-9.14, 38.71)),
    )
    sam.publish(title="Poles", content_type="application/geo+json", content=poles("P-101"), artifact_id=artifact)

    first = {t["id"]: t for t in sam.threads(artifact, version=1)["threads"]}  # type: ignore[union-attr]
    latest = {t["id"]: t for t in sam.threads(artifact)["threads"]}  # type: ignore[union-attr]
    feature, point = latest[on_feature["thread_id"]], latest[on_point["thread_id"]]

    assert feature["anchor"] == {"exact": "P-102", "prefix": "", "suffix": ""}
    assert feature["place"] == {
        "kind": "feature",
        "layer": "data",
        "id": "pole-102",
        "label": "P-102",
        "geometry": None,
    }
    assert point["anchor"]["exact"] == "38.71000° N, 9.14000° W"  # type: ignore[index]
    assert point["place"] == {"kind": "point", "geometry": {"type": "Point", "coordinates": [-9.14, 38.71]}}
    assert [first[t]["anchor_status"] for t in (on_feature["thread_id"], on_point["thread_id"])] == ["found", "found"]
    assert (feature["anchor_status"], point["anchor_status"]) == ("passage_gone", "found")
    assert [c["anchor_status"] for c in sam.feed()[:-1]] == ["passage_gone", "found"]


def test_a_place_is_a_feature_the_map_has_or_a_point_on_the_earth_of_a_map(agent: MakeAgent, ana: Store) -> None:
    content = json.dumps({"type": "Feature", "properties": {"name": "P-101"}, "geometry": None})
    sam = agent()
    on_map = str(sam.publish(title="Pole", content_type="application/geo+json", content=content)["artifact_id"])
    page = str(sam.publish(title="Page", content_type="text/html", content="<p>P-101</p>")["artifact_id"])

    named = ana.comment(on_map, None, "This one.", pick=Pick(PlaceKind.FEATURE, "P-101"))

    assert ana.threads(on_map)["threads"][0]["place"]["id"] == "P-101"  # type: ignore[index]
    assert named["thread_id"]
    refused(Code.ANCHOR_NOT_FOUND, lambda: ana.comment(on_map, None, "?", pick=Pick(PlaceKind.FEATURE, "P-999")))
    refused(Code.INVALID, lambda: ana.comment(on_map, None, "?", pick=Pick(PlaceKind.POINT, coordinates=(0, 91))))
    refused(Code.INVALID, lambda: ana.comment(page, None, "?", pick=Pick(PlaceKind.POINT, coordinates=(0, 0))))
