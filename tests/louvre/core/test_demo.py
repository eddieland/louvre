"""The demo: published once into any tables, and the same in memory as in Postgres."""

from louvre.core import demo
from louvre.core.accounts import reader_scope
from louvre.core.memory import MemoryTables
from louvre.core.postgres import PostgresTables
from louvre.core.store import Store
from louvre.core.tables import Tables


def test_the_demo_is_published_once(tables: Tables) -> None:
    first = demo.seed(tables)
    again = demo.seed(tables)

    assert (first, again) == (True, False)
    assert len(_dicts(_reader(tables).overview(namespace=demo.NAMESPACE)["artifacts"])) == 3


def test_the_demo_reads_alike_from_memory_and_postgres(postgres: PostgresTables) -> None:
    memory = MemoryTables()
    demo.seed(postgres)
    demo.seed(memory)

    assert _told(memory) == _told(postgres)
    assert [a["open_threads"] for a in _told(memory)[:3]] == [1, 1, 2]


def _reader(tables: Tables) -> Store:
    return Store(tables, reader_scope({demo.NAMESPACE}))


def _told(tables: Tables) -> list[dict[str, object]]:
    """Read what a reader of the demo sees, less the ids and times that differ between two seedings."""
    store = _reader(tables)
    seen: list[dict[str, object]] = []
    for artifact in _dicts(store.overview(namespace=demo.NAMESPACE)["artifacts"]):
        artifact_id = str(artifact["id"])
        seen.append(
            {
                "title": artifact["title"],
                "origin": artifact["origin"],
                "latest_version": artifact["latest_version"],
                "open_threads": artifact["open_threads"],
                "versions": [
                    (v["n"], v["content_type"], v["sha256"]) for v in _dicts(store.versions(artifact_id)["versions"])
                ],
                "threads": [
                    (t["anchor"], t["anchored_version"], t["state"], t["anchor_status"], _said(t["comments"]))
                    for t in _dicts(store.threads(artifact_id)["threads"])
                ],
                "first": store.read(artifact_id, 1)["text"],
            },
        )
    changes = [
        (c["kind"], c["state"], c["anchor_status"], c["body"], _dicts([c["author"]])[0]["display_name"])
        for c in store.feed()
        if c["kind"] != "end"
    ]
    return [*seen, {"feed": changes}]


def _said(comments: object) -> list[tuple[object, ...]]:
    return [
        (author["display_name"], author["kind"], author["on_behalf_of"], c["body"], c["via"])
        for c in _dicts(comments)
        for author in _dicts([c["author"]])
    ]


def _dicts(value: object) -> list[dict[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
