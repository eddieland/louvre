"""The demo: a few artifacts in the `demo` namespace, with threads on them, to show Louvre with nothing published yet.

Its people are accounts of their own, `demo:LOGIN`, whom nobody signs in as, and its agent writes for one of them, as
a token's would. Each part of it is published once: a part whose artifact the demo namespace holds already is left as
it is, so a database seeded before a part was added gets that part alone. Two processes seeding at once take a lock,
so one publishes and the other finds it there.

The design study the operator picked Louvre's look from (docs/ui-explorations/2026-10-23-directions) is its first
board: each direction at a laptop's size and a phone's, side by side, a row a direction (roadmap M3).
"""

import re
from importlib.resources import files

from louvre.core import explorations, style
from louvre.core.accounts import Account, person_scope, upsert_account
from louvre.core.boards import Board, Frame
from louvre.core.db import MIGRATE_LOCK, Connection
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
#: The design study the board shows, and its directions, by file name, with what the board calls each.
STUDY = "2026-10-23-directions"
DIRECTIONS = {"gallery": "Gallery", "studio": "Studio", "margins": "Margins"}
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
        )
        missing = [
            part for marker, part in parts if not agent.overview(origin=marker, namespace=NAMESPACE)["artifacts"]
        ]
        for part in missing:
            part(agent, people)
    finally:
        conn.execute("SELECT pg_advisory_unlock(%s)", (SEED_LOCK,))
    return bool(missing)


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
    for name, label in DIRECTIONS.items():
        page = explorations.find(STUDY, name)
        if page is None:
            continue
        published = agent.publish(
            title=f"Direction: {label}",
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
    """The report, in two versions: the second rewords a passage a thread is on, so that thread is gone from it."""
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

    second = first.replace("cache the quote per cart for 60 s", "cache the quote per cart for five minutes")
    agent.publish(title=title, content_type="text/html", content=second, artifact_id=artifact)
    agent.resolve(str(cache["thread_id"]), resolved=True)


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
    """An HTML page an agent wrote in the house style, from `style_get`."""
    template = (_FILES / "weekly-metrics.html.tmpl").read_text(encoding="utf-8")
    made = agent.publish(
        title="Payments, week 43",
        content_type="text/html",
        content=template.replace("{css}", style.CSS.rstrip()),
        origin={"canopy.report": "weekly"},
    )
    people["ana"].comment(
        str(made["artifact_id"]),
        Anchor.of("Declines at submit rose from 1.1% to 1.4%"),
        "Within what risk expected. Let's keep this line in next week's too.",
    )
