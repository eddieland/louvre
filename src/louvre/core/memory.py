"""The store's tables in this process's memory: the demo, for a deployment that has no database yet.

Nothing here outlives the process, and two processes each hold their own: what is written here is read by whoever
reaches the same process next, until it restarts. One lock makes every read and write one at a time, which is one
snapshot at a time. The store calls every method inside `read()`, `write()`, or `seeding()`, which hold it.
"""

import threading
from collections.abc import Iterable, Iterator, Mapping
from collections.abc import Set as AbstractSet
from contextlib import contextmanager
from datetime import datetime
from typing import override

from louvre.core.tables import Row, Tables
from louvre.core.text import Anchor


class MemoryTables(Tables):  # noqa: PLR0904  (one method a query: the interface is the tables')
    """The tables as dicts of rows by id, each in the order its rows were made, which is its `n`."""

    def __init__(self) -> None:
        """Start with every table empty."""
        self._lock = threading.RLock()
        self._artifacts: dict[str, Row] = {}
        self._versions: dict[tuple[str, int], Row] = {}
        self._threads: dict[str, Row] = {}
        self._comments: dict[str, Row] = {}
        self._changes: list[Row] = []
        self._authors: dict[str, Row] = {}
        self._accounts: dict[str, Row] = {}

    @override
    @contextmanager
    def read(self) -> Iterator[None]:
        with self._lock:
            yield

    @override
    @contextmanager
    def write(self) -> Iterator[None]:
        with self._lock:
            yield

    @override
    @contextmanager
    def seeding(self) -> Iterator[None]:
        with self._lock:
            yield

    @override
    def artifact(self, artifact_id: str) -> Row | None:
        row = self._artifacts.get(artifact_id)
        return None if row is None or row["deleted_at"] is not None else dict(row)

    @override
    def insert_artifact(
        self,
        artifact_id: str,
        namespace: str,
        title: str,
        origin: Mapping[str, str],
        owner_id: str | None,
        created_at: datetime,
    ) -> None:
        self._artifacts[artifact_id] = {
            "n": len(self._artifacts) + 1,
            "id": artifact_id,
            "namespace": namespace,
            "title": title,
            "origin": dict(origin),
            "latest_version": 1,
            "owner_id": owner_id,
            "created_at": created_at,
            "updated_at": created_at,
            "deleted_at": None,
        }

    @override
    def set_latest_version(self, artifact_id: str, version: int, title: str, updated_at: datetime) -> None:
        self._artifacts[artifact_id] |= {"latest_version": version, "title": title, "updated_at": updated_at}

    @override
    def delete_artifact(self, artifact_id: str, deleted_at: datetime) -> None:
        self._artifacts[artifact_id]["deleted_at"] = deleted_at

    @override
    def list_artifacts(
        self,
        *,
        namespaces: AbstractSet[str] | None,
        namespace: str | None,
        before: int | None,
        origin: Mapping[str, str],
        limit: int,
    ) -> list[Row]:
        listed = [
            {
                **row,
                "open_threads": sum(
                    1 for t in self._threads.values() if t["artifact_id"] == row["id"] and t["state"] == "open"
                ),
            }
            for row in reversed(self._artifacts.values())
            if row["deleted_at"] is None
            and _reaches(namespaces, row)
            and (namespace is None or row["namespace"] == namespace)
            and (before is None or _int(row["n"]) < before)
            and _holds(row["origin"], origin)
        ]
        return listed[:limit]

    @override
    def latest_texts(self, artifact_ids: AbstractSet[str]) -> dict[str, str]:
        texts: dict[str, str] = {}
        for artifact_id in artifact_ids:
            artifact = self._artifacts.get(artifact_id)
            if artifact is not None:
                texts[artifact_id] = str(self._versions[artifact_id, _int(artifact["latest_version"])]["text"])
        return texts

    @override
    def insert_version(
        self,
        artifact_id: str,
        n: int,
        content_type: str,
        sha256: str,
        content: str,
        text: str,
        created_at: datetime,
    ) -> None:
        self._versions[artifact_id, n] = {
            "artifact_id": artifact_id,
            "n": n,
            "content_type": content_type,
            "sha256": sha256,
            "content": content,
            "text": text,
            "created_at": created_at,
        }

    @override
    def version(self, artifact_id: str, n: int) -> Row | None:
        row = self._versions.get((artifact_id, n))
        return None if row is None else dict(row)

    @override
    def versions(self, artifact_id: str) -> list[Row]:
        return [
            {key: row[key] for key in ("artifact_id", "n", "content_type", "sha256", "created_at")}
            for (owner, _), row in self._versions.items()
            if owner == artifact_id
        ]

    @override
    def insert_thread(
        self,
        thread_id: str,
        artifact_id: str,
        anchor: Anchor | None,
        anchored_version: int,
        created_at: datetime,
    ) -> None:
        self._threads[thread_id] = {
            "n": len(self._threads) + 1,
            "id": thread_id,
            "artifact_id": artifact_id,
            "exact": None if anchor is None else anchor.exact,
            "prefix": None if anchor is None else anchor.prefix,
            "suffix": None if anchor is None else anchor.suffix,
            "anchored_version": anchored_version,
            "state": "open",
            "created_at": created_at,
        }

    @override
    def thread(self, thread_id: str) -> Row | None:
        row = self._threads.get(thread_id)
        if row is None:
            return None
        artifact = self._artifacts[str(row["artifact_id"])]
        return None if artifact["deleted_at"] is not None else {**row, "namespace": artifact["namespace"]}

    @override
    def threads(self, artifact_id: str, state: str | None) -> list[Row]:
        return [
            dict(row)
            for row in self._threads.values()
            if row["artifact_id"] == artifact_id and (state is None or row["state"] == state)
        ]

    @override
    def set_thread_state(self, thread_id: str, state: str) -> None:
        self._threads[thread_id]["state"] = state

    @override
    def insert_comment(
        self,
        comment_id: str,
        thread_id: str,
        author_id: str,
        body: str,
        created_at: datetime,
        via: str,
    ) -> None:
        self._comments[comment_id] = {
            "n": len(self._comments) + 1,
            "id": comment_id,
            "thread_id": thread_id,
            "seq": 0,
            "author_id": author_id,
            "body": body,
            "created_at": created_at,
            "edited_at": None,
            "deleted_at": None,
            "via": via,
        }

    @override
    def comment(self, comment_id: str) -> Row | None:
        row = self._comments.get(comment_id)
        if row is None or row["deleted_at"] is not None:
            return None
        thread = self._threads[str(row["thread_id"])]
        artifact = self._artifacts[str(thread["artifact_id"])]
        return None if artifact["deleted_at"] is not None else {**row, "namespace": artifact["namespace"]}

    @override
    def comments(self, artifact_id: str) -> list[Row]:
        return [
            {**row, **_author_columns(self._authors[str(row["author_id"])])}
            for row in self._comments.values()
            if self._threads[str(row["thread_id"])]["artifact_id"] == artifact_id
        ]

    @override
    def set_comment_seq(self, comment_id: str, seq: int) -> None:
        self._comments[comment_id]["seq"] = seq

    @override
    def edit_comment(self, comment_id: str, body: str, edited_at: datetime) -> None:
        self._comments[comment_id] |= {"body": body, "edited_at": edited_at}

    @override
    def delete_comment(self, comment_id: str, deleted_at: datetime) -> None:
        self._comments[comment_id] |= {"body": "", "deleted_at": deleted_at}

    @override
    def newest_seq(self) -> int:
        # A change is never deleted, so the newest `seq` is the count: `seq` is 1 for the first.
        return len(self._changes)

    @override
    def insert_change(
        self,
        kind: str,
        thread_id: str,
        comment_id: str | None,
        author_id: str,
        via: str,
        at: datetime,
    ) -> int:
        seq = len(self._changes) + 1
        self._changes.append(
            {
                "seq": seq,
                "kind": kind,
                "thread_id": thread_id,
                "comment_id": comment_id,
                "author_id": author_id,
                "via": via,
                "at": at,
            },
        )
        return seq

    @override
    def changes(
        self,
        *,
        since: int,
        through: int,
        namespaces: AbstractSet[str] | None,
        origin: Mapping[str, str],
        limit: int,
    ) -> list[Row]:
        listed: list[Row] = []
        # The change with `seq` s is at index s - 1, so these are the changes after `since` and up to `through`.
        for change in self._changes[since:through]:
            thread = self._threads[str(change["thread_id"])]
            artifact = self._artifacts[str(thread["artifact_id"])]
            if (
                artifact["deleted_at"] is not None
                or not _reaches(namespaces, artifact)
                or not _holds(artifact["origin"], origin)
            ):
                continue
            comment = None if change["comment_id"] is None else self._comments[str(change["comment_id"])]
            author = self._authors[str(change["author_id"])]
            listed.append(
                {
                    "seq": change["seq"],
                    "kind": change["kind"],
                    "at": change["at"],
                    "change_via": change["via"],
                    "artifact_id": artifact["id"],
                    "origin": artifact["origin"],
                    "thread_id": thread["id"],
                    "exact": thread["exact"],
                    "prefix": thread["prefix"],
                    "suffix": thread["suffix"],
                    "anchored_version": thread["anchored_version"],
                    "state": thread["state"],
                    "comment_id": None if comment is None else comment["id"],
                    "body": None if comment is None else comment["body"],
                    "created_at": None if comment is None else comment["created_at"],
                    "edited_at": None if comment is None else comment["edited_at"],
                    "deleted_at": None if comment is None else comment["deleted_at"],
                    "author_id": author["id"],
                    "display_name": author["display_name"],
                    "author_kind": author["kind"],
                    "on_behalf_of": author["on_behalf_of"],
                },
            )
            if len(listed) == limit:
                break
        return listed

    @override
    def upsert_author(self, author_id: str, display_name: str, kind: str, on_behalf_of: str | None) -> None:
        self._authors[author_id] = {
            "id": author_id,
            "display_name": display_name,
            "kind": kind,
            "on_behalf_of": on_behalf_of,
        }

    @override
    def upsert_account(self, account_id: str, login: str, display_name: str) -> None:
        self._accounts[account_id] = {"id": account_id, "login": login, "display_name": display_name}

    @override
    def account_names(self, account_ids: Iterable[str]) -> dict[str, str]:
        return {
            account_id: str(self._accounts[account_id]["display_name"])
            for account_id in account_ids
            if account_id in self._accounts
        }


def _reaches(namespaces: AbstractSet[str] | None, artifact: Row) -> bool:
    return namespaces is None or str(artifact["namespace"]) in namespaces


def _holds(origin: object, pairs: Mapping[str, str]) -> bool:
    """Say whether an artifact's origin holds every pair of `pairs`, as jsonb's `@>` does for flat pairs.

    Returns:
        Whether it does.
    """
    return isinstance(origin, dict) and all(origin.get(key) == value for key, value in pairs.items())


def _author_columns(author: Row) -> Row:
    return {key: author[key] for key in ("display_name", "kind", "on_behalf_of")}


def _int(value: object) -> int:
    assert isinstance(value, int)  # noqa: S101  (the column is an integer the tables themselves wrote)
    return value
