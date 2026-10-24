"""The demo: a few artifacts in the `demo` namespace, with threads on them, to show Louvre with nothing published yet.

Its people are accounts of their own, `demo:LOGIN`, whom nobody signs in as, and its agent writes for one of them, as
a token's would. Each part of it is published once: a part whose artifact the demo namespace holds already is left as
it is, so a database seeded before a part was added gets that part alone. Two processes seeding at once take a lock,
so one publishes and the other finds it there.

Its agent asks two decisions: which of the report's fixes ships first, open and waiting on Ana, and whether the release
notes ship, decided. They are seeded once too, after the artifacts they are asked on.

The design study the operator picked Louvre's look from (docs/ui-explorations/2026-10-23-directions) is its first
board: each direction at a laptop's size and a phone's, side by side, a row a direction (roadmap M3).
"""

import re
from importlib.resources import files

from louvre.core import explorations, style
from louvre.core.accounts import Account, person_scope, upsert_account
from louvre.core.boards import Board, Frame
from louvre.core.db import MIGRATE_LOCK, Connection
from louvre.core.decisions import Decisions, Option
from louvre.core.store import Author, Permission, Scope, Store, Via
from louvre.core.text import Anchor

#: The namespace the demo publishes in.
NAMESPACE = "demo"
#: The demo's people, by login.
PEOPLE = {
    "ana": Account("demo:ana", "ana", "Ana Ruiz"),
    "sam": Account("demo:sam", "sam", "Sam Okafor"),
    "raj": Account("demo:raj", "raj", "Raj Patel"),
}
#: The lock seeding takes: neither the migrations' nor the store's writes', which seeding itself takes.
SEED_LOCK = MIGRATE_LOCK + 2
#: The design study the board shows, and its directions, by file name, with the title each is published under.
STUDY = "2026-10-23-directions"
DIRECTIONS = {"gallery": "Direction: Gallery", "studio": "Direction: Studio", "margins": "Direction: Margins"}
#: The origin the study's artifacts carry; each adds `direction`, its file's name.
STUDY_ORIGIN = {"canopy.ticket": "LOUVRE-M1"}
#: The screens each direction is shown at on the board, left to right: a name, a label, a width and a height in CSS
#: pixels.
SCREENS = (("laptop", "Laptop, 1440", 1440, 900), ("phone", "Phone, 390", 390, 844))
#: The space between the board's frames, in CSS pixels: wide enough for a frame's label above it.
BOARD_GAP = 160
#: The demo's one board: the design study, a row a direction, its laptop beside its phone: a shape a phone's screen
#: and a laptop's both fit at a readable size.
BOARD = Board(
    id="design-study",
    title="Design study, 2026-10-23",
    namespace=NAMESPACE,
    frames=tuple(
        Frame(
            id=f"{name}-{screen}",
            label=label,
            origin={**STUDY_ORIGIN, "direction": name},
            x=column * (SCREENS[0][2] + BOARD_GAP),
            y=row * (SCREENS[0][3] + BOARD_GAP),
            width=width,
            height=height,
        )
        for row, name in enumerate(DIRECTIONS)
        for column, (screen, label, width, height) in enumerate(SCREENS)
    ),
)
#: Where the demo's pages are kept.
_FILES = files("louvre.core.demo")
#: A study page's links to Google's fonts, which an artifact's policy refuses: it loads nothing from the network.
_FONT_LINK = re.compile(r"\s*<link[^>]*fonts\.(?:googleapis|gstatic)\.com[^>]*>", re.IGNORECASE)


def seed(conn: Connection, *, base_url: str = "") -> bool:
    """Publish the demo, unless it is published already.

    Returns:
        Whether it was published now.
    """
    conn.execute("SELECT pg_advisory_lock(%s)", (SEED_LOCK,))
    try:
        for account in PEOPLE.values():
            upsert_account(conn, account)
        agent = Store(conn, _agent_scope(), base_url=base_url)
        people = {login: Store(conn, person_scope(account)) for login, account in PEOPLE.items()}
        # Each part by an origin pair its artifacts carry, oldest first, so the newest shows first in the list.
        parts = (
            (STUDY_ORIGIN, _study),
            ({"canopy.ticket": "PAY-142"}, _checkout),
            ({"canopy.ticket": "REL-2026.11"}, _release_notes),
            ({"canopy.report": "weekly"}, _weekly),
            ({"canopy.ticket": "PAY-151"}, _quote_cache),
            ({"canopy.ticket": "PAY-160"}, _vault_migration),
        )
        missing = [
            part for marker, part in parts if not agent.overview(origin=marker, namespace=NAMESPACE)["artifacts"]
        ]
        for part in missing:
            part(agent, people)
        unasked = not Decisions(agent).listed()["decisions"]
        if unasked:
            _decisions(agent, people)
    finally:
        conn.execute("SELECT pg_advisory_unlock(%s)", (SEED_LOCK,))
    return bool(missing) or unasked


def _agent_scope() -> Scope:
    sam = PEOPLE["sam"]
    return Scope(
        author=Author(f"agent:{sam.id}:canopy worker", "canopy worker", "agent", sam.id),
        via=Via.MCP,
        namespaces=frozenset({NAMESPACE}),
        home=NAMESPACE,
        permissions=frozenset(Permission),
        account_id=sam.id,
    )


def _study(agent: Store, people: dict[str, Store]) -> None:
    """The design study's three directions, the board's frames, with a thread on each of two."""
    made: dict[str, str] = {}
    for name, title in DIRECTIONS.items():
        page = explorations.find(STUDY, name)
        if page is None:
            continue
        published = agent.publish(
            title=title,
            content_type="text/html",
            content=_FONT_LINK.sub("", page.path.read_text(encoding="utf-8")),
            origin={**STUDY_ORIGIN, "direction": name},
        )
        made[name] = str(published["artifact_id"])
    if "gallery" in made:
        people["ana"].comment(
            made["gallery"],
            Anchor.of("This report traces where the time goes"),
            "The serif reads well at a phone's width too. This is the one I keep coming back to.",
        )
    if "studio" in made:
        people["raj"].comment(made["studio"], None, "Good for triage, but too much chrome for reading a report.")


def _checkout(agent: Store, people: dict[str, Store]) -> None:
    """The report, in two versions: the second rewords a passage a thread is on, so that thread is gone from it.

    The second also adds a sentence and drops a few words, as a revision answering its threads would, so comparing the
    two shows each kind of change.
    """
    first = (_FILES / "checkout-latency.html").read_text(encoding="utf-8")
    title = "Checkout latency: what we found and what to change"
    made = agent.publish(
        title=title,
        content_type="text/html",
        content=first,
        origin={"canopy.ticket": "PAY-142", "canopy.repo": "payments"},
    )
    artifact = str(made["artifact_id"])
    ana, sam, raj = people["ana"], people["sam"], people["raj"]

    cache = ana.comment(
        artifact,
        Anchor.of("cache the quote per cart for 60 s", "Warm the pool at deploy, and "),
        "Is 60 s long enough? Most carts sit for minutes before they pay.",
    )
    agent.reply(
        str(cache["thread_id"]),
        "Fair: the median cart pays after 3 minutes. I'll make it five, in the next version.",
    )

    provider = sam.comment(
        artifact,
        Anchor.of("The payment provider's own p95 held at 180 ms throughout"),
        "Which dashboard is this from? I'd like to link it in the incident review.",
    )
    agent.reply(str(provider["thread_id"]), "The provider's status panel, psp.latency, for 14 to 21 October.")

    fraud = ana.comment(
        artifact,
        Anchor.of("Move the fraud check back to submit time"),
        "Has the risk team signed off on this?",
    )
    sam.reply(str(fraud["thread_id"]), "Yes, on Friday. They asked us to watch declines at submit for a week.")
    sam.resolve(str(fraud["thread_id"]), resolved=True)

    raj.comment(artifact, None, "Clear write-up. Can this go into Thursday's incident review as it is?")

    # The second answers the threads: the cache's time, where the provider's figure is from; and drops an estimate.
    second = (
        first.replace("cache the quote per cart for 60 s", "cache the quote per cart for five minutes")
        .replace(
            "the provider is not the cause.",
            "the provider is not the cause. The figure is from its status panel, psp.latency, for 14 to 21 October.",
        )
        .replace("Alone, brings p95 under 700 ms. A day's work.", "Alone, brings p95 under 700 ms.")
    )
    assert second.count("five minutes") == second.count("psp.latency") == 1  # noqa: S101  (the page as written)
    agent.publish(title=title, content_type="text/html", content=second, artifact_id=artifact)
    agent.resolve(str(cache["thread_id"]), resolved=True)


def _decisions(agent: Store, people: dict[str, Store]) -> None:
    """The agent's two questions: which of the report's fixes ships first, and whether the notes ship.

    Each option of the first is on its step of the report. The second it closed once both people asked had answered.
    """
    asker = Decisions(agent)
    report = _newest(agent, {"canopy.ticket": "PAY-142"})
    if report is not None:
        fixes = asker.ask(
            report,
            "Which fix ships first?",
            (
                Option(
                    "Batch the tax quote",
                    "Alone, brings p95 under 700 ms.",
                    Anchor.of("Batch the tax quote into one call per cart"),
                ),
                Option(
                    "Warm the pool and cache the quote",
                    "Removes the cold start; the cache key needs the promotion's version.",
                    Anchor.of("Warm the pool at deploy"),
                ),
                Option(
                    "Move the fraud check",
                    "Back to submit time, where it ran before the release.",
                    Anchor.of("Move the fraud check back to submit time"),
                ),
            ),
            asked=["ana", "raj"],
        )
        decision = str(fixes["decision_id"])
        Decisions(people["raj"]).answer(decision, ["o1"], "It is most of the regression on its own.")
        Decisions(people["sam"]).answer(decision, ["o1"])
    notes = _newest(agent, {"canopy.ticket": "REL-2026.11"})
    if notes is not None:
        ship = asker.ask(
            notes,
            "Ship these notes with Thursday's release?",
            (Option("Ship them as they are"), Option("Hold them for the search fix")),
            asked=["ana", "raj"],
        )
        decision = str(ship["decision_id"])
        Decisions(people["ana"]).answer(decision, ["o1"], "The known issue says what to do meanwhile.")
        Decisions(people["raj"]).answer(decision, ["o1"])
        asker.close(decision, "o1", "Shipping Thursday; the search fix goes in the next notes.")


def _newest(agent: Store, origin: dict[str, str]) -> str | None:
    found = agent.overview(origin=origin, namespace=NAMESPACE)["artifacts"]
    return str(found[0]["id"]) if isinstance(found, list) and found and isinstance(found[0], dict) else None


def _release_notes(agent: Store, people: dict[str, Store]) -> None:
    """A Markdown draft, shown in the house style."""
    made = agent.publish(
        title="Release notes, 2026.11 (draft)",
        content_type="text/markdown",
        content=(_FILES / "release-notes.md").read_text(encoding="utf-8"),
        origin={"canopy.ticket": "REL-2026.11"},
    )
    artifact = str(made["artifact_id"])
    raj = people["raj"]
    raj.comment(
        artifact,
        Anchor.of("Signing out on one device no longer signs you out everywhere."),
        "Say why: people will read this as a security change.",
    )


def _weekly(agent: Store, people: dict[str, Store]) -> None:
    """A report an agent wrote in the house style, from `style_get`."""
    made = agent.publish(
        title="Payments, week 43",
        content_type="text/html",
        content=_styled("weekly-metrics.html.tmpl"),
        origin={"canopy.report": "weekly"},
    )
    people["ana"].comment(
        str(made["artifact_id"]),
        Anchor.of("Declines at submit rose from 1.1% to 1.4%"),
        "Within what risk expected. Let's keep this line in next week's too.",
    )


def _quote_cache(agent: Store, people: dict[str, Store]) -> None:
    """A decision in the house style: options side by side, one recommended, a thread answered on its cost."""
    made = agent.publish(
        title="Where should checkout cache tax quotes?",
        content_type="text/html",
        content=_styled("quote-cache.html.tmpl"),
        origin={"canopy.ticket": "PAY-151", "canopy.repo": "payments"},
    )
    artifact = str(made["artifact_id"])
    node = people["raj"].comment(
        artifact,
        Anchor.of("One small node is enough"),
        "We already run a Redis for sessions. Could quotes share it?",
    )
    agent.reply(
        str(node["thread_id"]),
        "They could, but a full cache evicts, and sessions would go with it. I'd keep them apart: the node is small.",
    )
    people["ana"].comment(artifact, None, "Redis, agreed. Ship it behind the flag.")


def _vault_migration(agent: Store, people: dict[str, Store]) -> None:
    """A plan in the house style: steps with their status, a risk, and a question a reader answers."""
    made = agent.publish(
        title="Stored cards move to the new provider by 15 December",
        content_type="text/html",
        content=_styled("vault-migration.html.tmpl"),
        origin={"canopy.ticket": "PAY-160", "canopy.repo": "payments"},
    )
    artifact = str(made["artifact_id"])
    people["sam"].comment(
        artifact,
        Anchor.of("Backfill the 1.2 million stored cards."),
        "The new provider rate-limits imports to 50 cards a second. Does the plan allow for that?",
    )
    people["ana"].comment(
        artifact,
        Anchor.of("Does finance need a reconciliation report for each step, or only at the end?"),
        "For each step: we close the month on the 3rd, and the backfill will straddle it.",
    )


def _styled(name: str) -> str:
    """Read one of the demo's pages, with the house style inlined where it says `{css}`.

    Returns:
        The page.
    """
    return (_FILES / name).read_text(encoding="utf-8").replace("{css}", style.CSS.rstrip())
