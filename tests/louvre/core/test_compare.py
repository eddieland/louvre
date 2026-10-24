"""What changed between two versions' texts: each change found in the later one, and nothing lost or made up."""

from collections.abc import Sequence

import pytest
from hypothesis import given
from hypothesis import strategies as st

from louvre.core import compare
from louvre.core.compare import Change, Kind
from louvre.core.text import Anchor, collapse, locate

#: A passage of a report, and a revision that rewrites one sentence, adds one, and drops another.
OLD = (
    "Checkout latency rose after the release. Warm the pool at deploy, and cache the quote per cart for 60 s. "
    "Move the fraud check back to submit time. Watch declines for a week."
)
NEW = (
    "Checkout latency rose after the release. Warm the pool at deploy, and cache the quote per cart for five minutes. "
    "The median cart pays after three minutes. Move the fraud check back to submit time."
)


def test_a_revision_reads_as_the_passages_it_changed() -> None:
    found = compare.compare(OLD, NEW)

    assert [(c.kind, c.removed, c.added) for c in found.changes] == [
        (
            Kind.CHANGED,
            "60 s.",
            "five minutes. The median cart pays after three minutes.",
        ),
        (Kind.REMOVED, "Watch declines for a week.", ""),
    ]
    assert (found.words_added, found.words_removed) == (9, 7)


def test_each_change_is_anchored_on_its_words_in_the_later_version() -> None:
    changed, removed = compare.compare(OLD, NEW).changes

    assert changed.anchor == Anchor.of(
        "five minutes. The median cart pays after three minutes.",
        "nd cache the quote per cart for",
        "Move the fraud check back to su",
    )
    assert changed.anchor is not None
    assert locate(NEW, changed.anchor) == changed.start == NEW.index("five minutes")
    # A removal at the end of the text is anchored on the word before where it was, and placed past the last word.
    assert removed.anchor is not None
    assert removed.anchor.exact == "time."
    assert removed.start == removed.end == len(NEW)


def test_a_removal_is_anchored_on_the_word_before_it() -> None:
    (removed,) = compare.compare("Keep this. Drop this sentence. Keep that.", "Keep this. Keep that.").changes

    assert (removed.kind, removed.removed) == (Kind.REMOVED, "Drop this sentence.")
    assert removed.anchor is not None
    assert removed.anchor.exact == "this."
    assert removed.anchor.suffix == "Keep that."
    # Its place is the space between the words either side of where it was.
    assert removed.start == removed.end == len("Keep this.")


def test_a_removal_at_the_start_is_anchored_on_the_word_after_it() -> None:
    (removed,) = compare.compare("Drop this. Keep that.", "Keep that.").changes

    assert removed.anchor is not None
    assert (removed.anchor.exact, removed.start) == ("Keep", 0)


def test_words_kept_between_two_close_changes_make_them_one() -> None:
    (change,) = compare.compare("We will retry it twice today.", "We may retry it once today.").changes

    assert (change.kind, change.removed, change.added) == (Kind.CHANGED, "will retry it twice", "may retry it once")


def test_three_words_kept_between_two_changes_keep_them_apart() -> None:
    found = compare.compare("We will retry the check twice today.", "We may retry the check once today.")

    assert [(c.removed, c.added) for c in found.changes] == [("will", "may"), ("twice", "once")]


def test_versions_alike_have_no_changes() -> None:
    assert compare.compare(OLD, OLD) == compare.Comparison(changes=(), words_added=0, words_removed=0)


def test_a_version_with_no_text_has_its_removal_anchored_nowhere() -> None:
    (removed,) = compare.compare("Every word goes.", "").changes

    assert (removed.kind, removed.anchor, removed.start) == (Kind.REMOVED, None, 0)


@pytest.mark.parametrize(
    ("start", "end", "touched"),
    [
        (0, 5, False),
        (NEW.index("cache"), NEW.index("five") + 4, True),
        (NEW.index("Move"), NEW.index("time."), False),
        (NEW.index("Move"), len(NEW), False),
    ],
)
def test_a_passage_is_touched_when_a_change_is_in_or_across_it(start: int, end: int, *, touched: bool) -> None:
    assert compare.compare(OLD, NEW).touches(start, end) is touched


def test_a_passage_is_touched_when_words_left_from_inside_it() -> None:
    new = "Keep this. Keep that."
    found = compare.compare("Keep this. Drop this sentence. Keep that.", new)

    assert found.touches(0, len(new)) is True
    assert found.touches(0, len("Keep this.")) is False


def test_too_many_words_are_refused() -> None:
    with pytest.raises(compare.TooLongError):
        compare.compare("word " * (compare.MAX_WORDS + 1), "word")


def test_a_page_of_one_sentence_over_and_over_is_compared_as_one_change() -> None:
    old = " ".join(["The cat sat."] * 20_000)
    new = " ".join(["The cat sat."] * 10_000 + ["A dog ran."] + ["The cat sat."] * 10_000)

    (change,) = compare.compare(old, new).changes

    assert (change.kind, change.added) == (Kind.ADDED, "A dog ran.")


#: Texts of a few words from a small vocabulary, so two often share words and repeat them.
texts = st.lists(st.sampled_from(["the", "cat", "sat.", "on", "a", "mat", "dog", "ran."]), max_size=40).map(" ".join)


@given(old=texts, new=texts)
def test_putting_back_what_each_change_removed_rebuilds_the_earlier_text(old: str, new: str) -> None:
    found = compare.compare(old, new)

    assert _rebuilt(new, found.changes) == old
    for change in found.changes:
        assert new[change.start : change.end] == change.added
        assert change.anchor is None or change.anchor.exact in new


def _rebuilt(new: str, changes: Sequence[Change]) -> str:
    """Put each change's removed words back in place of its added ones in `new`.

    Returns:
        The text, whitespace collapsed.
    """
    pieces: list[str] = []
    at = 0
    for change in changes:
        pieces += [new[at : change.start], change.removed]
        at = change.end
    pieces.append(new[at:])
    return collapse(" ".join(pieces))
