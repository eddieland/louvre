"""The skills in `skills/` name only what Louvre serves: its tools, and the house style's kinds of artifact."""

import re
from pathlib import Path

from louvre.core import style
from louvre.mcp.tools import TOOLS

#: The repository's root in a checkout.
ROOT = Path(__file__).resolve().parents[2]
#: The skill for building artifacts.
ARTIFACTS = ROOT / "skills" / "louvre-artifacts" / "SKILL.md"


def test_the_artifacts_skill_names_only_tools_louvre_serves() -> None:
    text = ARTIFACTS.read_text(encoding="utf-8")
    named = set(re.findall(r"`((?:artifact|thread|comment|style|decision|board|presence)_[a-z]+)`", text))
    arguments = {field for t in TOOLS for field in t.request.model_fields}

    assert named - arguments
    assert named - arguments - {t.name for t in TOOLS} == set()


def test_the_artifacts_skill_names_every_kind_the_style_has() -> None:
    text = ARTIFACTS.read_text(encoding="utf-8")

    assert {kind for kind in style.Kind if f"`{kind}`" not in text} == set()


def test_each_skill_names_itself_as_its_directory_is_named() -> None:
    for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
        front = path.read_text(encoding="utf-8").split("---\n")[1]

        assert f"name: {path.parent.name}\n" in front
        assert re.search(r"^description: \S", front, re.MULTILINE)
