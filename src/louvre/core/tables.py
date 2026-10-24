"""The rows the store reads and writes, behind one interface, so one `Store` runs on Postgres or in memory.

`louvre.core.store` holds the contract: what a call may do, what it checks, and what it answers. The tables hold rows
and nothing more: each method is one query, named for the rows it finds or changes. `louvre.core.postgres` keeps them
in Postgres (D007), where Louvre's data lives; `louvre.core.memory` keeps them in this process, for the demo when a
deployment has no database yet. Every row is a dict by column name, with the columns the migrations give the table.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from collections.abc import Set as AbstractSet
from contextlib import AbstractContextManager
from datetime import datetime

from louvre.core.text import Anchor

#: A row, by column name.
type Row = dict[str, object]


class Tables(ABC):  # noqa: PLR0904  (one method a query, so an implementation is only queries)
    """The store's tables: artifacts, versions, threads, comments, changes, authors, and the people agents write for."""

    @abstractmethod
    def read(self) -> AbstractContextManager[None]:
        """Read in one snapshot: every query inside the block sees the same rows.

        Returns:
            The block to read in.
        """

    @abstractmethod
    def write(self) -> AbstractContextManager[None]:
        """Write one at a time: every block waits for the one before it, so `seq` commits in order.

        Returns:
            The block to write in, which commits when it ends. The store checks before it writes, so a block that
            raises has written nothing.
        """

    @abstractmethod
    def seeding(self) -> AbstractContextManager[None]:
        """Hold every other seeder off while the demo is checked for and published, over several writes.

        Returns:
            The block to seed in.
        """

    @abstractmethod
    def artifact(self, artifact_id: str) -> Row | None:
        """Find an artifact that is not deleted.

        Returns:
            Its row, or None.
        """

    @abstractmethod
    def insert_artifact(  # noqa: PLR0917  (a row's columns)
        self,
        artifact_id: str,
        namespace: str,
        title: str,
        origin: Mapping[str, str],
        owner_id: str | None,
        created_at: datetime,
    ) -> None:
        """Make an artifact, at version 1."""

    @abstractmethod
    def set_latest_version(self, artifact_id: str, version: int, title: str, updated_at: datetime) -> None:
        """Note that an artifact's latest version is `version`, titled `title`."""

    @abstractmethod
    def delete_artifact(self, artifact_id: str, deleted_at: datetime) -> None:
        """Delete an artifact: its row stays, marked, and no query finds it again."""

    @abstractmethod
    def list_artifacts(
        self,
        *,
        namespaces: AbstractSet[str] | None,
        namespace: str | None,
        before: int | None,
        origin: Mapping[str, str],
        limit: int,
    ) -> list[Row]:
        """List the artifacts that are not deleted, newest first.

        Returns:
            At most `limit` rows, each with `open_threads`, its count of open threads: those in `namespaces` (every
            one for None), in `namespace` when it is given, with `n` below `before` when it is given, and whose origin
            holds every pair of `origin`.
        """

    @abstractmethod
    def latest_texts(self, artifact_ids: AbstractSet[str]) -> dict[str, str]:
        """Read the text of each artifact's latest version.

        Returns:
            The text by artifact id, for the ids found.
        """

    @abstractmethod
    def insert_version(  # noqa: PLR0917  (a row's columns)
        self,
        artifact_id: str,
        n: int,
        content_type: str,
        sha256: str,
        content: str,
        text: str,
        created_at: datetime,
    ) -> None:
        """Add a version to an artifact."""

    @abstractmethod
    def version(self, artifact_id: str, n: int) -> Row | None:
        """Find a version of an artifact.

        Returns:
            Its row, or None.
        """

    @abstractmethod
    def versions(self, artifact_id: str) -> list[Row]:
        """List an artifact's versions, oldest first, without their content.

        Returns:
            Their rows.
        """

    @abstractmethod
    def insert_thread(
        self,
        thread_id: str,
        artifact_id: str,
        anchor: Anchor | None,
        anchored_version: int,
        created_at: datetime,
    ) -> None:
        """Open a thread on an artifact, on a passage or, with no anchor, on the whole of it."""

    @abstractmethod
    def thread(self, thread_id: str) -> Row | None:
        """Find a thread on an artifact that is not deleted.

        Returns:
            Its row, with its artifact's `namespace`, or None.
        """

    @abstractmethod
    def threads(self, artifact_id: str, state: str | None) -> list[Row]:
        """List an artifact's threads, oldest first, those in `state` when it is given.

        Returns:
            Their rows.
        """

    @abstractmethod
    def set_thread_state(self, thread_id: str, state: str) -> None:
        """Resolve a thread, or reopen it."""

    @abstractmethod
    def insert_comment(  # noqa: PLR0917  (a row's columns)
        self,
        comment_id: str,
        thread_id: str,
        author_id: str,
        body: str,
        created_at: datetime,
        via: str,
    ) -> None:
        """Add a comment to a thread, with no `seq` yet."""

    @abstractmethod
    def comment(self, comment_id: str) -> Row | None:
        """Find a comment that is not deleted, on an artifact that is not deleted.

        Returns:
            Its row, with its artifact's `namespace`, or None.
        """

    @abstractmethod
    def comments(self, artifact_id: str) -> list[Row]:
        """List every comment on an artifact's threads, oldest first.

        Returns:
            Their rows, each with its author's `display_name`, `kind`, and `on_behalf_of`.
        """

    @abstractmethod
    def set_comment_seq(self, comment_id: str, seq: int) -> None:
        """Give a comment the `seq` of the change that made it."""

    @abstractmethod
    def edit_comment(self, comment_id: str, body: str, edited_at: datetime) -> None:
        """Change a comment's text."""

    @abstractmethod
    def delete_comment(self, comment_id: str, deleted_at: datetime) -> None:
        """Delete a comment: its row stays, with its body empty."""

    @abstractmethod
    def newest_seq(self) -> int:
        """Find the newest change's `seq`.

        Returns:
            It, or 0 before any change.
        """

    @abstractmethod
    def insert_change(  # noqa: PLR0917  (a row's columns)
        self,
        kind: str,
        thread_id: str,
        comment_id: str | None,
        author_id: str,
        via: str,
        at: datetime,
    ) -> int:
        """Record a change to a thread, or to a comment in it.

        Returns:
            Its `seq`, the next of one sequence across the store.
        """

    @abstractmethod
    def changes(
        self,
        *,
        since: int,
        through: int,
        namespaces: AbstractSet[str] | None,
        origin: Mapping[str, str],
        limit: int,
    ) -> list[Row]:
        """List the changes with `seq` after `since` and up to `through`, oldest first.

        Returns:
            At most `limit` rows, on artifacts that are not deleted, in `namespaces` (every one for None), and whose
            origin holds every pair of `origin`: each change's columns, its `via` as `change_via`, its artifact's
            `artifact_id` and `origin`, its thread's anchor columns and `state`, its comment's `comment_id`, `body`,
            `created_at`, `edited_at`, and `deleted_at` (None for a change to a thread), and its author's
            `author_id`, `display_name`, `kind` as `author_kind`, and `on_behalf_of`.
        """

    @abstractmethod
    def upsert_author(self, author_id: str, display_name: str, kind: str, on_behalf_of: str | None) -> None:
        """Record an author as it is now: a person, or an agent writing for one."""

    @abstractmethod
    def upsert_account(self, account_id: str, login: str, display_name: str) -> None:
        """Record a person as their provider names them now."""

    @abstractmethod
    def account_names(self, account_ids: Iterable[str]) -> dict[str, str]:
        """Find people's names, for the comments agents write for them.

        Returns:
            Each id found, with its person's name.
        """
