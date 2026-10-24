"""The demo: a few artifacts in the `demo` namespace, with threads on them, to show Louvre with nothing published yet.

Its people are accounts of their own, `demo:LOGIN`, whom nobody signs in as, and its agent writes for one of them, as
a token's would. It is published once: seeding tables whose demo namespace has an artifact in it does nothing, and two
processes seeding one database at once take a lock, so one publishes it and the other finds it there. A deployment
with no database seeds it into memory (louvre.core.memory), where it is all there is to read.
"""

from importlib.resources import files

from louvre.core import style
from louvre.core.accounts import Account, person_scope
from louvre.core.store import Author, Permission, Scope, Store, Via
from louvre.core.tables import Tables
from louvre.core.text import Anchor

#: The namespace the demo publishes in.
NAMESPACE = "demo"
#: The demo's people, by login.
PEOPLE = {
    "ana": Account("demo:ana", "ana", "Ana Ruiz"),
    "sam": Account("demo:sam", "sam", "Sam Okafor"),
    "raj": Account("demo:raj", "raj", "Raj Patel"),
}
#: Where the demo's pages are kept.
_FILES = files("louvre.core.demo")


def seed(tables: Tables, *, base_url: str = "") -> bool:
    """Publish the demo in `tables`, unless it is published there already.

    Returns:
        Whether it was published now.
    """
    with tables.seeding():
        for account in PEOPLE.values():
            tables.upsert_account(account.id, account.login, account.display_name)
        agent = Store(tables, _agent_scope(), base_url=base_url)
        if agent.overview(namespace=NAMESPACE)["artifacts"]:
            return False
        people = {login: Store(tables, person_scope(account)) for login, account in PEOPLE.items()}
        _checkout(agent, people)
        _release_notes(agent, people)
        _weekly(agent, people)
    return True


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
