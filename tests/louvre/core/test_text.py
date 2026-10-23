import json
from pathlib import Path

import pytest

from louvre.core.text import Anchor, collapse, locate, visible_text

#: The cases louvre.core.text and the bridge both answer (ui/src/bridge/text.test.ts reads the same file).
CASES = json.loads((Path(__file__).parents[2] / "fixtures" / "anchors.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_the_shared_cases(case: dict[str, object]) -> None:
    text = visible_text(str(case["html"]))

    assert text == case["text"]
    anchors = case["anchors"]
    assert isinstance(anchors, list)
    for found in anchors:
        anchor = Anchor.of(found["exact"], found.get("prefix", ""), found.get("suffix", ""))
        assert locate(text, anchor) == found["at"], found


def test_an_empty_anchor_is_found_nowhere() -> None:
    assert locate("some words", Anchor("")) is None


def test_collapse_trims_and_joins_whitespace() -> None:
    assert collapse("  a \n\t b  ") == "a b"
