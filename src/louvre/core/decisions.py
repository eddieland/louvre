"""Decisions: a question asked on an artifact, for people to answer by choosing, and read back by who asked (U7).

An agent, or a person, asks a question on an artifact with two or more options, each a label, a line of detail, and
the passage of the artifact it is about, if any; it may name the people it asks. A signed-in person answers on the
web by choosing one option, or several where the question allows, with a note, and may change their answer while the
decision is open. An agent never answers: a decision is how people tell agents what they chose. Whoever asked, or the
person they asked for, closes it, naming the option decided on if there is one.

Its asker reads it back: whole, by id; listed, by artifact or origin; or as a feed. The feed is the comment feed's
shape (louvre.core.store): one `seq` across every decision, in commit order, each page ending with an `end` line. It
is its own feed, so the contract's `comment_feed` carries the kinds canopy's readers know and no others (D011). An
event keeps what it said when it was made, so an answer changed is two events, the second the answer now.
"""

import json
import secrets
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from louvre.core.store import (
    MAX_BODY,
    MAX_FEED,
    Code,
    Permission,
    Refused,
    Row,
    Store,
    Via,
    bounded,
    check_anchor,
    iso,
)
from louvre.core.text import Anchor, locate

#: The most characters of a question, an option's label, and its detail.
MAX_QUESTION = 500
MAX_LABEL = 120
MAX_DETAIL = 500
#: How many options a decision has, at least and at most.
MIN_OPTIONS = 2
MAX_OPTIONS = 12
#: The most people a decision asks, and the most characters of a login.
MAX_ASKED = 20
MAX_LOGIN = 64
#: The most decisions a list holds: the newest.
LIST_MOST = 100


class Event(StrEnum):
    """What happened to a decision, as its feed says."""

    #: It was asked.
    ASKED = "decision_asked"
    #: A person answered it, or changed their answer.
    ANSWERED = "decision_answered"
    #: It was closed.
    CLOSED = "decision_closed"


@dataclass(frozen=True)
class Option:
    """One choice a decision offers, as its asker gives it."""

    #: What it is, in a few words.
    label: str
    #: A line more about it; empty for none.
    detail: str = ""
    #: The passage of the artifact it is about, in its latest version; None for none.
    anchor: Anchor | None = None


class Decisions:
    """The decisions a store's scope reaches, held to that scope as its other records are."""

    def __init__(self, store: Store) -> None:
        """Serve the decisions on the artifacts `store` reaches."""
        self._store = store
        self._conn = store.connection

    def ask(
        self,
        artifact_id: str,
        question: str,
        options: Sequence[Option],
        *,
        multiple: bool = False,
        asked: Iterable[str] = (),
    ) -> dict[str, object]:
        """Ask a question on an artifact's latest version.

        Returns:
            The decision's id, its event's `seq`, and the url of the page it is answered on.

        Raises:
            Refused: `read_only` without comment; `invalid` for a blank question or label, fewer options than
                `MIN_OPTIONS`, two options alike, or a login that is no login; `too_long` for a question, label,
                detail, anchor, or list of options or people over its bound; `not_found` or `out_of_scope` for the
                artifact; `anchor_not_found` for an option's passage not in its latest version.
        """
        store = self._store
        store.require(Permission.COMMENT)
        _check_question(question, options)
        logins = _logins(asked)
        with store.writing():
            artifact = store.artifact_row(artifact_id)
            latest = int(str(artifact["latest_version"]))
            text = store.version_text(artifact_id, latest)
            for option in options:
                if option.anchor is not None and locate(text, option.anchor) is None:
                    raise Refused(
                        Code.ANCHOR_NOT_FOUND,
                        f"the passage of option {option.label!r} is not in version {latest} of {artifact_id}",
                    )
            decision_id = f"d_{secrets.token_hex(8)}"
            self._conn.execute(
                "INSERT INTO decisions (id, artifact_id, question, options, multiple, asked, author_id, account_id,"
                " version, state, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'open', %s)",
                (
                    decision_id,
                    artifact_id,
                    question,
                    json.dumps([_option_json(f"o{i}", o) for i, o in enumerate(options, 1)]),
                    multiple,
                    logins,
                    store.author_id(),
                    store.scope.account_id,
                    latest,
                    _now(),
                ),
            )
            seq = self._event(Event.ASKED, decision_id)
        return {"decision_id": decision_id, "seq": seq, "url": self.url(artifact_id, decision_id)}

    def read(self, decision_id: str) -> dict[str, object]:
        """Read a decision whole.

        Returns:
            The decision: its question, its options each with how many chose it, who was asked and whether they
            answered, every answer, and its state; with what the scope's person chose, and whether the scope may
            close it.

        Raises:
            Refused: `not_found` or `out_of_scope` for the decision.
        """
        with self._store.reading():
            row = self._decision(decision_id)
            [shown] = self._shaped([row])
        return shown

    def listed(
        self,
        *,
        artifact_id: str | None = None,
        origin: Mapping[str, str] | None = None,
        state: str | None = None,
    ) -> dict[str, object]:
        """List the decisions the scope reaches, newest first, on one artifact or those whose origin holds `origin`.

        Returns:
            At most `LIST_MOST` decisions, each as `read` gives it, and how many open ones await the scope's person.

        Raises:
            Refused: `not_found` or `out_of_scope` for the artifact.
        """
        store = self._store
        with store.reading():
            if artifact_id is not None:
                store.artifact_row(artifact_id)
            rows = self._conn.execute(
                "SELECT d.*, a.title AS artifact_title, a.namespace, a.latest_version FROM decisions d"
                " JOIN artifacts a ON a.id = d.artifact_id WHERE a.deleted_at IS NULL"
                " AND (%(all)s OR a.namespace = ANY(%(namespaces)s))"
                " AND (%(artifact)s::text IS NULL OR d.artifact_id = %(artifact)s)"
                " AND (%(state)s::text IS NULL OR d.state = %(state)s) AND a.origin @> %(filter)s::jsonb"
                " ORDER BY d.n DESC LIMIT %(limit)s",
                {
                    "artifact": artifact_id,
                    "state": state,
                    "filter": json.dumps(dict(origin or {})),
                    "limit": LIST_MOST,
                }
                | store.reach(),
            ).fetchall()
            shaped = self._shaped(rows)
            waiting = self._awaiting()
        return {"decisions": shaped, "awaiting": waiting}

    def answer(self, decision_id: str, choices: Sequence[str], note: str = "") -> dict[str, object]:
        """Answer a decision, as a person on the web, or change one's answer while it is open.

        Returns:
            The answer's event's `seq`.

        Raises:
            Refused: `read_only` for an agent, or a scope that may not comment; `not_found` or `out_of_scope` for
                the decision; `closed` for a decision closed; `invalid` for no choice, more than one where one is
                asked for, or a choice it does not offer; `too_long` for the note.
        """
        store = self._store
        scope = store.scope
        store.require(Permission.COMMENT)
        if scope.via != Via.WEB or scope.account_id is None or scope.author.kind != "person":
            raise Refused(Code.READ_ONLY, "a person answers a decision, on the web; an agent reads the answers")
        bounded("note", note, MAX_BODY)
        with store.writing():
            row = self._decision(decision_id, locked=True)
            if row["state"] != "open":
                raise Refused(Code.CLOSED, f"{decision_id} is closed")
            chosen = _choices(row, choices)
            self._conn.execute(
                "INSERT INTO answers (decision_id, account_id, author_id, choices, note, answered_at)"
                " VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (decision_id, account_id) DO UPDATE SET"
                " author_id = excluded.author_id, choices = excluded.choices, note = excluded.note,"
                " answered_at = excluded.answered_at",
                (decision_id, scope.account_id, store.author_id(), chosen, note.strip(), _now()),
            )
            seq = self._event(Event.ANSWERED, decision_id, chosen, note.strip())
        return {"seq": seq}

    def close(self, decision_id: str, outcome: str | None = None, note: str = "") -> dict[str, object]:
        """Close a decision, naming the option decided on, if one was, and saying why.

        Returns:
            Its state, and its event's `seq`.

        Raises:
            Refused: `read_only` without comment; `not_found` or `out_of_scope` for the decision; `out_of_scope` when
                the scope neither asked it nor acts for the person who did; `closed` for one closed already;
                `invalid` for an outcome it does not offer; `too_long` for the note.
        """
        store = self._store
        store.require(Permission.COMMENT)
        bounded("note", note, MAX_BODY)
        with store.writing():
            row = self._decision(decision_id, locked=True)
            if not self._may_close(row):
                raise Refused(Code.OUT_OF_SCOPE, f"{decision_id} is closed by who asked it, or the person they act for")
            if row["state"] != "open":
                raise Refused(Code.CLOSED, f"{decision_id} is closed already")
            chosen = [] if outcome is None else _choices({**row, "multiple": False}, [outcome])
            self._conn.execute(
                "UPDATE decisions SET state = 'closed', outcome = %s, outcome_note = %s, closed_at = %s WHERE id = %s",
                (outcome, note.strip(), _now(), decision_id),
            )
            seq = self._event(Event.CLOSED, decision_id, chosen, note.strip())
        return {"state": "closed", "seq": seq}

    def feed(self, origin: Mapping[str, str] | None = None, since: int = 0, limit: int = MAX_FEED) -> list[object]:
        """Read the events after `since` on the decisions the scope reaches whose artifacts' origin holds `origin`.

        Returns:
            At most `limit` events, oldest first, then the `end` line naming the `seq` the page covers through, as the
            comment feed's does.

        Raises:
            Refused: `invalid` for a limit outside 1 to `MAX_FEED`, or a `since` that is no seq.
        """
        if not 1 <= limit <= MAX_FEED or not 0 <= since < 2**63:
            raise Refused(Code.INVALID, f"since is a seq from 0, and limit from 1 to {MAX_FEED}")
        store = self._store
        with store.reading():
            row = self._conn.execute("SELECT coalesce(max(seq), 0) AS newest FROM decision_events").fetchone()
            newest = int(str(row["newest"])) if row else 0
            rows = self._conn.execute(
                "SELECT e.seq, e.kind, e.at, e.choices, e.note, d.id AS decision_id, d.artifact_id, a.origin,"
                " d.question, d.state, d.outcome, w.id AS author_id, w.display_name, w.kind AS author_kind,"
                " w.on_behalf_of FROM decision_events e JOIN decisions d ON d.id = e.decision_id"
                " JOIN artifacts a ON a.id = d.artifact_id JOIN authors w ON w.id = e.author_id"
                " WHERE e.seq > %(since)s AND e.seq <= %(newest)s AND a.deleted_at IS NULL"
                " AND (%(all)s OR a.namespace = ANY(%(namespaces)s)) AND a.origin @> %(filter)s::jsonb"
                " ORDER BY e.seq LIMIT %(limit)s",
                {"since": since, "newest": newest, "filter": json.dumps(dict(origin or {})), "limit": limit}
                | store.reach(),
            ).fetchall()
        through = int(str(rows[-1]["seq"])) if len(rows) == limit else max(newest, since)
        return [*(_event_json(r) for r in rows), {"kind": "end", "through": through}]

    def url(self, artifact_id: str, decision_id: str) -> str:
        """Name the page a decision is answered on: its artifact's, opened at it.

        Returns:
            Its URL on Louvre's web pages.
        """
        return f"{self._store.base_url}/a/{artifact_id}?decision={decision_id}"

    def _decision(self, decision_id: str, *, locked: bool = False) -> Row:
        """Find a decision on an artifact the scope reaches, and lock its row until the write commits if `locked`.

        Returns:
            Its row, with its artifact's title and latest version.

        Raises:
            Refused: `not_found` for no such decision, `out_of_scope` for one outside the scope.
        """
        row = self._conn.execute(
            "SELECT d.*, a.title AS artifact_title, a.namespace, a.latest_version FROM decisions d"  # noqa: S608
            " JOIN artifacts a ON a.id = d.artifact_id WHERE d.id = %s AND a.deleted_at IS NULL"
            # Constant SQL; values are bound. FOR NO KEY UPDATE, as the store's writes lock rows (louvre.core.store).
            + (" FOR NO KEY UPDATE OF d" if locked else ""),
            (decision_id,),
        ).fetchone()
        if row is None:
            raise Refused(Code.NOT_FOUND, f"no decision {decision_id!r}")
        self._store.reaches(str(row["namespace"]), decision_id)
        return row

    def _shaped(self, rows: Sequence[Row]) -> list[dict[str, object]]:
        """Shape decisions as `read` gives them, reading their answers and people in one query each.

        Returns:
            The decisions, in the order of `rows`.
        """
        ids = [str(r["id"]) for r in rows]
        answers = self._conn.execute(
            "SELECT x.*, c.display_name FROM answers x JOIN accounts c ON c.id = x.account_id"
            " WHERE x.decision_id = ANY(%s) ORDER BY x.answered_at",
            (ids,),
        ).fetchall()
        authors = self._conn.execute(
            "SELECT DISTINCT w.* FROM authors w JOIN decisions d ON d.author_id = w.id WHERE d.id = ANY(%s)",
            (ids,),
        ).fetchall()
        logins = sorted({str(login) for r in rows for login in _strings(r["asked"])})
        people = self._conn.execute(
            "SELECT id, lower(login) AS login, display_name FROM accounts WHERE lower(login) = ANY(%s)",
            (logins,),
        ).fetchall()
        by_author = {str(w["id"]): w for w in authors}
        own = self._own_login()
        shaped: list[dict[str, object]] = []
        for row in rows:
            mine = [a for a in answers if a["decision_id"] == row["id"]]
            shaped.append(self._json(row, mine, by_author[str(row["author_id"])], people, own))
        return shaped

    def _json(
        self,
        row: Row,
        answers: Sequence[Row],
        author: Row,
        people: Sequence[Row],
        own_login: str | None,
    ) -> dict[str, object]:
        account = self._store.scope.account_id
        counts: dict[str, int] = {}
        for answer in answers:
            for choice in _strings(answer["choices"]):
                counts[choice] = counts.get(choice, 0) + 1
        answered = {str(a["account_id"]) for a in answers}
        asked = []
        for login in _strings(row["asked"]):
            # Two accounts may share a login, one from each way of signing in: either answering counts.
            accounts = sorted(
                (p for p in people if p["login"] == login),
                key=lambda p: str(p["id"]) not in answered,
            )
            asked.append(
                {
                    "login": login,
                    "name": accounts[0]["display_name"] if accounts else None,
                    "answered": any(str(p["id"]) in answered for p in accounts),
                },
            )
        own = next((a for a in answers if a["account_id"] == account), None)
        return {
            "id": row["id"],
            "artifact_id": row["artifact_id"],
            "artifact_title": row["artifact_title"],
            "question": row["question"],
            "multiple": row["multiple"],
            "version": row["version"],
            "options": [{**o, "count": counts.get(str(o["id"]), 0)} for o in _options(row)],
            "asked": asked,
            "author": {
                "id": author["id"],
                "display_name": author["display_name"],
                "kind": author["kind"],
                "on_behalf_of": author["on_behalf_of"],
            },
            "state": row["state"],
            "outcome": row["outcome"],
            "outcome_note": row["outcome_note"],
            "created_at": iso(row["created_at"]),
            "closed_at": iso(row["closed_at"]),
            "answers": [
                {
                    "account_id": a["account_id"],
                    "name": a["display_name"],
                    "choices": _strings(a["choices"]),
                    "note": a["note"],
                    "answered_at": iso(a["answered_at"]),
                }
                for a in answers
            ],
            "url": self.url(str(row["artifact_id"]), str(row["id"])),
            "mine": None if own is None else {"choices": _strings(own["choices"]), "note": own["note"]},
            "awaits_me": row["state"] == "open" and own is None and own_login in _strings(row["asked"]),
            "may_close": row["state"] == "open" and self._may_close(row),
        }

    def _own_login(self) -> str | None:
        """Find the login of the scope's person, lowercase, as decisions ask people by.

        Returns:
            It, or None for a scope with no person.
        """
        account = self._store.scope.account_id
        if account is None:
            return None
        row = self._conn.execute("SELECT lower(login) AS login FROM accounts WHERE id = %s", (account,)).fetchone()
        return None if row is None else str(row["login"])

    def _awaiting(self) -> int:
        """Count the open decisions the scope reaches that ask its person and that they have not answered.

        Returns:
            The count; 0 for a scope with no person.
        """
        account = self._store.scope.account_id
        if account is None:
            return 0
        row = self._conn.execute(
            "SELECT count(*) AS n FROM decisions d JOIN artifacts a ON a.id = d.artifact_id"
            " JOIN accounts c ON c.id = %(account)s WHERE d.state = 'open' AND a.deleted_at IS NULL"
            " AND lower(c.login) = ANY(d.asked) AND (%(all)s OR a.namespace = ANY(%(namespaces)s))"
            " AND NOT EXISTS (SELECT 1 FROM answers x WHERE x.decision_id = d.id AND x.account_id = %(account)s)",
            {"account": account} | self._store.reach(),
        ).fetchone()
        return int(str(row["n"])) if row else 0

    def _may_close(self, row: Row) -> bool:
        scope = self._store.scope
        return row["author_id"] == scope.author.id or (
            scope.account_id is not None and row["account_id"] == scope.account_id
        )

    def _event(self, kind: Event, decision_id: str, choices: Collection[str] = (), note: str = "") -> int:
        """Record an event by the scope's author, inside a write, in `seq` order (louvre.core.store).

        Returns:
            Its `seq`.
        """
        author_id = self._store.in_order()
        row = self._conn.execute(
            "INSERT INTO decision_events (kind, decision_id, author_id, choices, note, at)"
            " VALUES (%s, %s, %s, %s, %s, %s) RETURNING seq",
            (kind.value, decision_id, author_id, list(choices), note, _now()),
        ).fetchone()
        return int(str(row["seq"])) if row else 0


def _check_question(question: str, options: Sequence[Option]) -> None:
    """Hold a question and its options to their bounds.

    Raises:
        Refused: `invalid` for a blank question or label, too few options, or two alike; `too_long` past a bound.
    """
    if not question.strip():
        raise Refused(Code.INVALID, "a decision's question must not be blank")
    bounded("question", question, MAX_QUESTION)
    if len(options) < MIN_OPTIONS:
        raise Refused(Code.INVALID, f"a decision offers at least {MIN_OPTIONS} options")
    if len(options) > MAX_OPTIONS:
        raise Refused(Code.TOO_LONG, f"a decision offers at most {MAX_OPTIONS} options")
    labels: set[str] = set()
    for option in options:
        label = " ".join(option.label.split()).casefold()
        if not label:
            raise Refused(Code.INVALID, "an option's label must not be blank")
        if label in labels:
            raise Refused(Code.INVALID, f"two options are labeled {option.label!r}")
        labels.add(label)
        bounded("option's label", option.label, MAX_LABEL)
        bounded("option's detail", option.detail, MAX_DETAIL)
        if option.anchor is not None:
            check_anchor(option.anchor)


def _logins(asked: Iterable[str]) -> list[str]:
    """Read the logins of the people a decision asks, lowercase, each once, in the order given.

    Returns:
        The logins.

    Raises:
        Refused: `invalid` for a login that is blank or holds whitespace; `too_long` for too many, or one too long.
    """
    found: list[str] = []
    for given in asked:
        login = given.strip().lstrip("@").lower()
        if not login or any(c.isspace() for c in login):
            raise Refused(Code.INVALID, f"{given!r} is not a login")
        bounded("login", login, MAX_LOGIN)
        if login not in found:
            found.append(login)
    if len(found) > MAX_ASKED:
        raise Refused(Code.TOO_LONG, f"a decision asks at most {MAX_ASKED} people")
    return found


def _choices(row: Mapping[str, object], choices: Sequence[str]) -> list[str]:
    """Check choices against what a decision offers.

    Returns:
        The choices, each once, in the order the decision offers them.

    Raises:
        Refused: `invalid` for no choice, more than one where one is asked for, or one it does not offer.
    """
    offered = [str(o["id"]) for o in _options(row)]
    unknown = [c for c in choices if c not in offered]
    if unknown:
        raise Refused(Code.INVALID, f"no option {unknown[0]!r}; the options are {', '.join(offered)}")
    chosen = [o for o in offered if o in choices]
    if not chosen:
        raise Refused(Code.INVALID, "an answer chooses an option")
    if len(chosen) > 1 and not row["multiple"]:
        raise Refused(Code.INVALID, "this decision takes one choice")
    return chosen


def _option_json(option_id: str, option: Option) -> dict[str, object]:
    anchor = option.anchor
    return {
        "id": option_id,
        "label": " ".join(option.label.split()),
        "detail": option.detail.strip(),
        "anchor": None if anchor is None else {"exact": anchor.exact, "prefix": anchor.prefix, "suffix": anchor.suffix},
    }


def _options(row: Mapping[str, object]) -> list[dict[str, object]]:
    value = row["options"]
    return [o for o in value if isinstance(o, dict)] if isinstance(value, list) else []


def _strings(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _event_json(row: Row) -> dict[str, object]:
    return {
        "kind": row["kind"],
        "seq": row["seq"],
        "at": iso(row["at"]),
        "decision_id": row["decision_id"],
        "artifact_id": row["artifact_id"],
        "origin": row["origin"],
        "question": row["question"],
        "state": row["state"],
        "outcome": row["outcome"],
        "author": {
            "id": row["author_id"],
            "display_name": row["display_name"],
            "kind": row["author_kind"],
            "on_behalf_of": row["on_behalf_of"],
        },
        "choices": _strings(row["choices"]),
        "note": row["note"],
    }


def _now() -> datetime:
    return datetime.now(UTC)
