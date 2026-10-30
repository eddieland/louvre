"""Presence: which agents are at work on an artifact now, and at what (REQUIREMENTS U14).

An agent is present on an artifact from its own calls, without saying so: each tool call that names the artifact, by
its id or by a thread or a decision on it, keeps the agent present there for `NOTED_FOR`, as `here`, so an agent
written against canopy's contract alone shows where it works. One that says more calls `presence_set`: it is
reading, revising, or replying in a thread, with a line of note, for as long as it names; its calls keep it present
meanwhile, and the call that does what it said, a version published or a comment written, brings it back to `here`,
as an assistant's "is thinking" clears when it answers. Saying it is done ends its presence at once.

Nothing outlives its expiry: a read leaves out a presence past it, and the next call writes over it afresh, so no page
says an agent is working after it has stopped. Every time is the database's, so every instance of the app agrees on
what has expired. A presence is the moment's, never a record: it is in no feed and no inbox, and it is not kept past
the next call. A call is noted at most once in `NOTED_EVERY` on each artifact, so an agent reading a page's threads
over and over writes almost nothing.
"""

from datetime import timedelta
from enum import StrEnum

from louvre.core.store import Code, Permission, Refused, Row, Store, Via, bounded, iso

#: How long a call keeps its agent present on the artifacts it names.
NOTED_FOR = timedelta(minutes=2)
#: How often a call is noted at most, on each artifact: a presence is seen to the nearest of these.
NOTED_EVERY = timedelta(seconds=15)
#: How long an activity an agent says lasts, unless it names another, and the least and the most it may name.
SAID_FOR = timedelta(minutes=5)
LEAST_FOR = timedelta(seconds=10)
MOST_FOR = timedelta(minutes=15)
#: The most characters of an activity's note: a line.
MAX_NOTE = 140


class Activity(StrEnum):
    """What an agent present on an artifact is doing there."""

    #: Present from its calls, saying nothing more.
    HERE = "here"
    #: Reading the artifact, or its threads.
    READING = "reading"
    #: Writing a new version of it.
    REVISING = "revising"
    #: Writing a reply in one of its threads.
    REPLYING = "replying"


def noted(store: Store, completes: Activity | None = None) -> None:
    """Note that an agent's call, through `store`, named the artifacts it found, each by its id or a record's on it.

    An activity the agent said that has expired, or that `completes` names, as a publish completes revising, is
    `here` again. A call by a person, on the web, notes nothing: only agents are present.
    """
    author = store.scope.author
    if store.scope.via != Via.MCP or author.kind != "agent" or author.on_behalf_of is None or not store.named:
        return
    # Once the call did what was said, or the presence expired, it starts again as here.
    again = "(p.expires_at <= now() OR p.activity = %(completes)s)"
    with store.writing():
        store.connection.execute(
            "INSERT INTO presence AS p (artifact_id, author_id, display_name, on_behalf_of, activity, note,"  # noqa: S608  (constant SQL; values are bound)
            " thread_id, since, seen_at, expires_at)"
            " SELECT a.id, %(author)s, %(name)s, %(for)s, %(here)s, '', NULL, now(), now(), now() + %(noted_for)s"
            " FROM artifacts a WHERE a.id = ANY(%(ids)s) AND a.deleted_at IS NULL"
            # In one order, so two calls by one agent on the same artifacts never wait on each other in turn.
            " ORDER BY a.id"
            " ON CONFLICT (artifact_id, author_id) DO UPDATE SET"
            f" activity = CASE WHEN {again} THEN %(here)s ELSE p.activity END,"
            f" note = CASE WHEN {again} THEN '' ELSE p.note END,"
            f" thread_id = CASE WHEN {again} THEN NULL ELSE p.thread_id END,"
            f" since = CASE WHEN {again} THEN now() ELSE p.since END,"
            " display_name = excluded.display_name, seen_at = now(),"
            " expires_at = greatest(p.expires_at, now() + %(noted_for)s)"
            # Written once in a while, or whenever it would expire sooner than the call keeps it.
            " WHERE p.seen_at <= now() - %(every)s OR p.expires_at < now() + %(noted_for)s - %(every)s"
            " OR p.activity = %(completes)s",
            {
                "author": author.id,
                "name": author.display_name,
                "for": author.on_behalf_of,
                "here": Activity.HERE.value,
                "noted_for": NOTED_FOR,
                "every": NOTED_EVERY,
                "ids": sorted(store.named),
                "completes": None if completes is None else completes.value,
            },
        )


class Presence:
    """The agents present on the artifacts a store's scope reaches, held to that scope as its other records are."""

    def __init__(self, store: Store) -> None:
        """Serve presence through `store`, held to its scope."""
        self._store = store

    def say(
        self,
        artifact_id: str,
        activity: Activity | None,
        *,
        note: str = "",
        thread_id: str | None = None,
        lasting: timedelta = SAID_FOR,
    ) -> dict[str, object]:
        """Say what the scope's agent is doing on an artifact, for `lasting`; None for nothing, as it leaves.

        Returns:
            The artifact's id, the activity, `done` for none, and while present, its note, its thread, and when it
            expires.

        Raises:
            Refused: `read_only` for a scope that is no agent's; `out_of_scope` for one that may not read, or an
                artifact outside it; `not_found` for no such artifact, or a thread not on it; `too_long` for a note
                over its bound; `invalid` for a thread with an activity but replying, replying with none, or a time
                outside the bounds.
        """
        store = self._store
        author = store.scope.author
        if author.kind != "agent" or author.on_behalf_of is None:
            raise Refused(Code.READ_ONLY, "only an agent is present on an artifact")
        store.require(Permission.READ, Code.OUT_OF_SCOPE)
        bounded("note", note, MAX_NOTE)
        if (activity == Activity.REPLYING) != (thread_id is not None):
            raise Refused(Code.INVALID, "replying names the thread it is in, and only replying names one")
        if not LEAST_FOR <= lasting <= MOST_FOR:
            raise Refused(Code.INVALID, f"an activity lasts {LEAST_FOR.seconds} to {MOST_FOR.seconds} seconds")
        with store.writing():
            store.artifact_row(artifact_id)
            if (
                thread_id is not None
                and not store.connection.execute(
                    "SELECT 1 FROM threads WHERE id = %s AND artifact_id = %s",
                    (thread_id, artifact_id),
                ).fetchone()
            ):
                raise Refused(Code.NOT_FOUND, f"no thread {thread_id!r} on {artifact_id}")
            if activity is None:
                store.connection.execute(
                    "DELETE FROM presence WHERE artifact_id = %s AND author_id = %s",
                    (artifact_id, author.id),
                )
                return {"artifact_id": artifact_id, "activity": "done"}
            row = store.connection.execute(
                "INSERT INTO presence AS p (artifact_id, author_id, display_name, on_behalf_of, activity, note,"
                " thread_id, since, seen_at, expires_at)"
                " VALUES (%(artifact)s, %(author)s, %(name)s, %(for)s, %(activity)s, %(note)s, %(thread)s, now(),"
                " now(), now() + %(lasting)s)"
                " ON CONFLICT (artifact_id, author_id) DO UPDATE SET"
                # The same activity, said again while it lasts, keeps the time it started.
                " since = CASE WHEN p.expires_at > now() AND p.activity = excluded.activity"
                " AND p.thread_id IS NOT DISTINCT FROM excluded.thread_id THEN p.since ELSE now() END,"
                " activity = excluded.activity, note = excluded.note, thread_id = excluded.thread_id,"
                " display_name = excluded.display_name, seen_at = now(), expires_at = excluded.expires_at"
                " RETURNING expires_at",
                {
                    "artifact": artifact_id,
                    "author": author.id,
                    "name": author.display_name,
                    "for": author.on_behalf_of,
                    "activity": activity.value,
                    "note": note,
                    "thread": thread_id,
                    "lasting": lasting,
                },
            ).fetchone()
        assert row is not None  # noqa: S101  (an upsert returns its row)
        return {
            "artifact_id": artifact_id,
            "activity": activity.value,
            "note": note,
            "thread_id": thread_id,
            "expires_at": iso(row["expires_at"]),
        }

    def present(self, artifact_id: str) -> list[dict[str, object]]:
        """List the agents present on an artifact, the longest at their activity first.

        Returns:
            Each agent, as a comment's author is named, with the person it works for named too; its activity, note,
            and thread; since when it has been at it; when it last called; and when it is gone unless it calls again.

        Raises:
            Refused: `out_of_scope` for a scope that may not read, or an artifact outside it; `not_found` for none.
        """
        store = self._store
        with store.reading():
            store.artifact_row(artifact_id)
            rows = store.connection.execute(
                "SELECT p.*, a.display_name AS on_behalf_of_name FROM presence p"
                " JOIN accounts a ON a.id = p.on_behalf_of"
                " WHERE p.artifact_id = %s AND p.expires_at > now() ORDER BY p.since, p.author_id",
                (artifact_id,),
            ).fetchall()
        return [_present_json(row) for row in rows]


def _present_json(row: Row) -> dict[str, object]:
    return {
        "author": {
            "id": row["author_id"],
            "display_name": row["display_name"],
            "kind": "agent",
            "on_behalf_of": row["on_behalf_of"],
            "on_behalf_of_name": row["on_behalf_of_name"],
        },
        "activity": row["activity"],
        "note": row["note"],
        "thread_id": row["thread_id"],
        "since": iso(row["since"]),
        "seen_at": iso(row["seen_at"]),
        "expires_at": iso(row["expires_at"]),
    }
