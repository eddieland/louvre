"""What changed from one version of an artifact to a later one: their texts compared word by word (REQUIREMENTS U8).

Two versions are compared as their readers see them, by their texts (louvre.core.text): words parted by single spaces,
so markup, scripts, and reflowed whitespace never show as a change. The words both share at the start and at the end
are set aside first, since a revision mostly changes a few passages of a long page. The rest is compared with the
stdlib's `difflib` in two passes, as word-by-word alone takes seconds on a long page: first by chunks of words, each
ending after a sentence's last word or at a word its own hash picks, so an insertion moves no chunk's end but its own;
then word by word inside each stretch of chunks that differ, unless it is longer than `_REFINE` words, when it is one
change. Two changes with fewer than `_MERGE` words between them are one, so a sentence rewritten reads as one rewrite,
not as a scatter of words around the few it kept.

Each change is anchored in the later version as a thread is, by its words and the text either side of them, so the
artifact's page finds and marks it with the bridge as it marks a thread's passage. A removal has no words there of its
own: it is anchored on the word before the place its words were, so its note sits level with the line they left, or
on the word after it at the text's start.
"""

import itertools
import zlib
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum

from louvre.core.text import CONTEXT, Anchor

#: The most words either version's text may have to be compared: a long report has a few thousand.
MAX_WORDS = 400_000
#: Two changes with fewer words than this between them are one change.
_MERGE = 3
#: The longest stretch of differing chunks, in words either side, that is compared word by word.
_REFINE = 2000
#: A word ends a chunk when its hash is a multiple of this, so a chunk is this many words long at most, on average.
_CHUNK = 12
#: A word ending in one of these ends a sentence, and its chunk.
_STOPS = (".", "!", "?", ":", ";")


class TooLongError(ValueError):
    """A version's text has more than `MAX_WORDS` words to compare."""


class Kind(StrEnum):
    """What a change did to the earlier version's words."""

    #: Words the later version has where the earlier had none.
    ADDED = "added"
    #: Words the earlier version had where the later has none.
    REMOVED = "removed"
    #: Words the later version has in place of others.
    CHANGED = "changed"


@dataclass(frozen=True)
class Change:
    """One passage that differs between the two versions."""

    kind: Kind
    #: Finds it in the later version: its words there, or for a removal the word before where they were. None when the
    #: later version has no text at all.
    anchor: Anchor | None
    #: The words the earlier version had here; empty for an addition.
    removed: str
    #: The words the later version has here; empty for a removal.
    added: str
    #: Where its words are in the later version's text: the first character's index, and one past the last. A removal
    #: has no words there, so both are the place they were.
    start: int
    end: int


@dataclass(frozen=True)
class Comparison:
    """Every change from one version's text to a later one's, in the later one's order."""

    changes: Sequence[Change]
    #: How many words the changes add, and how many they remove.
    words_added: int
    words_removed: int

    def touches(self, start: int, end: int) -> bool:
        """Say whether a passage of the later version's text, from `start` to `end`, is in or across a change.

        Returns:
            True when it overlaps words added or changed, or words were removed from between its first and last.
        """
        return any(
            start < change.end and change.start < end if change.start < change.end else start < change.start < end
            for change in self.changes
        )


def compare(old: str, new: str) -> Comparison:
    """Compare an earlier version's text, `old`, with a later one's, `new`.

    Returns:
        The changes, each anchored in `new`.

    Raises:
        TooLongError: Either text has more than `MAX_WORDS` words.
    """
    a, b = _words(old), _words(new)
    if max(len(a), len(b)) > MAX_WORDS:
        raise TooLongError(f"a version has more than {MAX_WORDS} words to compare")
    starts = _starts(b)
    changes = tuple(_change(new, a, b, starts, op) for op in _merged(_opcodes(a, b)))
    return Comparison(
        changes=changes,
        words_added=sum(len(_words(c.added)) for c in changes),
        words_removed=sum(len(_words(c.removed)) for c in changes),
    )


#: A stretch of words that differs: where it is in the earlier version's words, then in the later's, end exclusive.
type _Op = tuple[int, int, int, int]


def _words(text: str) -> list[str]:
    # A version's text is collapsed: its words are parted by one space, and it has none at its ends.
    return text.split(" ") if text else []


def _starts(words: Sequence[str]) -> list[int]:
    """Find where each word starts in the text it was split from, its words parted by one space.

    Returns:
        Each word's first character's index.
    """
    starts: list[int] = []
    at = 0
    for word in words:
        starts.append(at)
        at += len(word) + 1
    return starts


def _opcodes(a: Sequence[str], b: Sequence[str]) -> list[_Op]:
    """Find the stretches of words that differ, the words both texts start and end with set aside first.

    Returns:
        Each stretch, in order.
    """
    lo = 0
    most = min(len(a), len(b))
    while lo < most and a[lo] == b[lo]:
        lo += 1
    hi = 0
    while hi < most - lo and a[-1 - hi] == b[-1 - hi]:
        hi += 1
    a_ends, b_ends = _chunks(a, lo, len(a) - hi), _chunks(b, lo, len(b) - hi)
    a_chunks = [" ".join(a[s:e]) for s, e in itertools.pairwise(a_ends)]
    b_chunks = [" ".join(b[s:e]) for s, e in itertools.pairwise(b_ends)]
    ops: list[_Op] = []
    # With autojunk: a chunk in more than one in a hundred of a long page's is never where a match starts. Without it, a
    # page of one sentence over and over takes minutes to compare, and prose seldom repeats a sentence.
    for i1, i2, j1, j2 in _differing(a_chunks, b_chunks, autojunk=True):
        ops += _refined(a, b, (a_ends[i1], a_ends[i2], b_ends[j1], b_ends[j2]))
    return ops


def _chunks(words: Sequence[str], start: int, end: int) -> list[int]:
    """Part words from `start` to `end` into chunks, each ending after a sentence's last word or a word its hash picks.

    Returns:
        Where each chunk starts, then `end`.
    """
    ends = [start]
    for i in range(start, end):
        word = words[i]
        if word.endswith(_STOPS) or zlib.crc32(word.encode()) % _CHUNK == 0:
            ends.append(i + 1)
    if ends[-1] != end:
        ends.append(end)
    return ends


def _differing(a: Sequence[str], b: Sequence[str], *, autojunk: bool) -> list[_Op]:
    matcher = SequenceMatcher(None, a, b, autojunk=autojunk)
    return [(i1, i2, j1, j2) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]


def _refined(a: Sequence[str], b: Sequence[str], op: _Op) -> list[_Op]:
    """Compare a stretch of differing chunks word by word, unless it is too long to, when it is one change.

    Returns:
        The stretches of words in it that differ.
    """
    i1, i2, j1, j2 = op
    if i1 == i2 or j1 == j2 or max(i2 - i1, j2 - j1) > _REFINE:
        return [op]
    # Without autojunk: it would take a page's common words, "the" among them, for junk that a match never starts on.
    words = _differing(a[i1:i2], b[j1:j2], autojunk=False)
    return [(i1 + p1, i1 + p2, j1 + q1, j1 + q2) for p1, p2, q1, q2 in words]


def _merged(ops: Sequence[_Op]) -> list[_Op]:
    """Join each stretch to the one before it when fewer than `_MERGE` words part them.

    Returns:
        The stretches, joined.
    """
    merged: list[_Op] = []
    for i1, i2, j1, j2 in ops:
        if merged and i1 - merged[-1][1] < _MERGE:
            p1, _, q1, _ = merged[-1]
            merged[-1] = (p1, i2, q1, j2)
        else:
            merged.append((i1, i2, j1, j2))
    return merged


def _change(new: str, a: Sequence[str], b: Sequence[str], starts: Sequence[int], op: _Op) -> Change:
    i1, i2, j1, j2 = op
    removed, added = " ".join(a[i1:i2]), " ".join(b[j1:j2])
    kind = Kind.REMOVED if not added else Kind.ADDED if not removed else Kind.CHANGED
    if j2 > j1:
        start, end = starts[j1], starts[j2 - 1] + len(b[j2 - 1])
        return Change(kind, _anchor(new, start, end), removed, added, start, end)
    # A removal: the place its words were, anchored on the word before it, or the one after it at the text's start.
    at = starts[j1] - 1 if j1 < len(b) else len(new)
    at = max(at, 0)
    if not b:
        return Change(kind, None, removed, added, at, at)
    k = j1 - 1 if j1 > 0 else j1
    return Change(kind, _anchor(new, starts[k], starts[k] + len(b[k])), removed, added, at, at)


def _anchor(text: str, start: int, end: int) -> Anchor:
    return Anchor.of(text[start:end], text[max(0, start - CONTEXT) : start], text[end : end + CONTEXT])
