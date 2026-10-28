r"""Search across artifacts: one found by the words of its title, its latest version, or comments (REQUIREMENTS U12).

A query is words, each matched without regard to case at the start of a word, so `retr` finds "retry" and "retries"
but not "metric". An artifact is found when each word is in its title, its latest version's text, or a comment on it
that is not deleted. What is quoted of it is where they were: its title, a few passages of its latest version, and a
few comments, those holding the most of the words first, each as runs of text with the words found marked.

Postgres and Python match a word alike: its pattern, `(?<!\w)` and the word escaped, is a regular expression in both,
so a passage Louvre quotes is one the database found.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Self

from louvre.core.db import Connection

#: The most characters a query may hold, and the most words.
MAX_QUERY = 200
MAX_WORDS = 8
#: The most passages and comments quoted of each artifact found.
QUOTED = 3
#: How many characters a passage quotes on either side of the words it was found by, and a comment.
AROUND = 70
AROUND_COMMENT = 160
#: What stands for words a quote leaves out at either end.
ELLIPSIS = "\N{HORIZONTAL ELLIPSIS}"

#: What parts words.
_SPACE = re.compile(r"\s+")
#: A run of a quote: its text, and `hit` when it is a word the query found.
type Run = dict[str, object]


@dataclass(frozen=True)
class Query:
    """What a reader searches for: words, each found at the start of a word, in any case."""

    #: The words, each once, in the order given.
    words: Sequence[str]

    @classmethod
    def of(cls, text: str) -> Self:
        """Read a query as a reader types it: words parted by spaces, each kept once.

        Returns:
            The query, with no words for a blank one.
        """
        return cls(tuple(dict.fromkeys(word.lower() for word in text.split())))

    @property
    def patterns(self) -> list[str]:
        """Each word as a regular expression Postgres and Python read alike: at a word's start, the word itself."""
        return [_pattern(word) for word in self.words]

    def runs(self, text: str) -> list[Run]:
        """Part `text` into runs, the words found marked.

        Returns:
            The runs, in order, together all of `text`; one unmarked run when nothing is found.
        """
        found: list[Run] = []
        at = 0
        for match in self._matcher().finditer(text):
            if match.start() > at:
                found.append({"text": text[at : match.start()]})
            found.append({"text": match.group(), "hit": True})
            at = match.end()
        if at < len(text) or not found:
            found.append({"text": text[at:]})
        return found

    def passages(self, text: str) -> list[list[Run]]:
        """Quote the passages of `text` the words are found in, in its order, at most `QUOTED`.

        Each passage is the words found and `AROUND` characters on either side, to a word's end, its whitespace made
        single spaces; passages that would overlap are one.

        Returns:
            Each passage's runs.
        """
        windows: list[tuple[int, int]] = []
        for match in self._matcher().finditer(text):
            start, end = _widened(text, match.start(), match.end(), AROUND)
            if windows and start <= windows[-1][1]:
                windows[-1] = (windows[-1][0], max(end, windows[-1][1]))
            elif len(windows) == QUOTED:
                break
            else:
                windows.append((start, end))
        return [self.runs(_quoted(text, start, end)) for start, end in windows]

    def excerpt(self, text: str) -> list[Run]:
        """Quote a comment around the first word found in it, `AROUND_COMMENT` characters on either side.

        Returns:
            Its runs: the comment whole, when it is that short.
        """
        match = self._matcher().search(text)
        start, end = (0, len(text)) if match is None else _widened(text, match.start(), match.end(), AROUND_COMMENT)
        return self.runs(_quoted(text, start, end))

    def _matcher(self) -> re.Pattern[str]:
        # The longest word first, so a word that begins another is marked as the longer where both are found.
        words = sorted(self.words, key=len, reverse=True)
        return re.compile(r"(?<!\w)(?:" + "|".join(re.escape(word) for word in words) + ")", re.IGNORECASE)


#: A query of no words, which every artifact answers.
EVERYTHING = Query(())


def found(conn: Connection, artifact_ids: Sequence[str], query: Query) -> dict[str, dict[str, object]]:
    """Find where the query's words are in each artifact named, inside the transaction that listed them.

    Returns:
        By artifact id, those with words found in their latest version or their comments: `passages`, the latest
        version's, and `comments`, each with its thread, its author, and its excerpt's runs.
    """
    params = {"ids": list(artifact_ids), "patterns": query.patterns, "quoted": QUOTED}
    texts = conn.execute(
        "SELECT a.id, v.text FROM artifacts a JOIN versions v ON v.artifact_id = a.id AND v.n = a.latest_version"
        " WHERE a.id = ANY(%(ids)s) AND EXISTS (SELECT 1 FROM unnest(%(patterns)s::text[]) p WHERE v.text ~* p)",
        params,
    ).fetchall()
    # The comments holding the most of the words first, then the newest.
    comments = conn.execute(
        "SELECT * FROM (SELECT t.artifact_id, t.id AS thread_id, c.id AS comment_id, c.body, w.id AS author_id,"
        " w.display_name, w.kind, w.on_behalf_of,"
        " row_number() OVER (PARTITION BY t.artifact_id ORDER BY h.hits DESC, c.n DESC) AS k"
        " FROM threads t JOIN comments c ON c.thread_id = t.id JOIN authors w ON w.id = c.author_id,"
        " LATERAL (SELECT count(*) AS hits FROM unnest(%(patterns)s::text[]) p WHERE c.body ~* p) h"
        " WHERE t.artifact_id = ANY(%(ids)s) AND c.deleted_at IS NULL AND h.hits > 0) ranked"
        " WHERE k <= %(quoted)s ORDER BY artifact_id, k",
        params,
    ).fetchall()
    passages = {str(row["id"]): query.passages(str(row["text"])) for row in texts}
    quoted: dict[str, list[dict[str, object]]] = {}
    for row in comments:
        quoted.setdefault(str(row["artifact_id"]), []).append(
            {
                "thread_id": row["thread_id"],
                "comment_id": row["comment_id"],
                "author": {
                    "id": row["author_id"],
                    "display_name": row["display_name"],
                    "kind": row["kind"],
                    "on_behalf_of": row["on_behalf_of"],
                },
                "body": query.excerpt(str(row["body"])),
            },
        )
    return {
        artifact_id: {"passages": passages.get(artifact_id, []), "comments": quoted.get(artifact_id, [])}
        for artifact_id in artifact_ids
        if artifact_id in passages or artifact_id in quoted
    }


def _pattern(word: str) -> str:
    """Write a word as a regular expression that finds it at a word's start.

    `re.escape` escapes only what is not a letter, a digit, or `_`, and a backslash before such a character is that
    character in Postgres's expressions too.

    Returns:
        The expression.
    """
    return r"(?<!\w)" + re.escape(word)


def _widened(text: str, start: int, end: int, around: int) -> tuple[int, int]:
    """Widen `text[start:end]` by up to `around` characters on either side, to whole words.

    Returns:
        The widened start and end.
    """
    before = max(0, start - around)
    if before > 0:
        space = _SPACE.search(text, before, start)
        before = start if space is None else space.end()
    after = min(len(text), end + around)
    if after < len(text):
        spaces = list(_SPACE.finditer(text, end, after))
        after = spaces[-1].start() if spaces else end
    return before, after


def _quoted(text: str, start: int, end: int) -> str:
    """Quote `text[start:end]` on one line, an ellipsis at each end that leaves words out.

    Returns:
        The quote.
    """
    words = " ".join(text[start:end].split())
    return (ELLIPSIS if start > 0 else "") + words + (ELLIPSIS if end < len(text) else "")
