"""The UI explorations under `docs/ui-explorations/`, which the preview deployment serves to compare on a phone.

In a source checkout they sit at the repository root. In an installed wheel they are bundled inside the package
(`louvre/_data/explorations`, see `[tool.hatch.build.targets.wheel.force-include]` in pyproject.toml), which is how
they reach Vercel.
"""

import re
from dataclasses import dataclass
from pathlib import Path

# This file is louvre/web/explorations.py; bundled files sit beside the top-level package.
_PACKAGE = Path(__file__).resolve().parent.parent
_CANDIDATES = (_PACKAGE / "_data" / "explorations", _PACKAGE.parent.parent / "docs" / "ui-explorations")
_TITLE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class Exploration:
    """One page of an exploration."""

    #: The exploration's directory, such as `2026-10-23-directions`.
    group: str
    #: The page's file name without `.html`, such as `studio`.
    name: str
    #: The page's `<title>`, or its name when it has none.
    title: str
    #: Where the page is on disk.
    path: Path


def all_pages() -> list[Exploration]:
    """List every exploration's pages, the newest exploration first.

    Returns:
        The pages, or none when this installation has no explorations.
    """
    root = next((c for c in _CANDIDATES if c.is_dir()), None)
    if root is None:
        return []
    pages: list[Exploration] = []
    for group in sorted((d for d in root.iterdir() if d.is_dir()), reverse=True):
        for path in sorted(group.glob("*.html")):
            match = _TITLE.search(path.read_text(encoding="utf-8"))
            title = match.group(1).strip() if match else path.stem
            pages.append(Exploration(group=group.name, name=path.stem, title=title, path=path))
    return pages


def find(group: str, name: str) -> Exploration | None:
    """Find one page by its exploration and name, among the pages listed, so no path from a URL reaches the disk.

    Returns:
        The page, or None when there is none by that name.
    """
    return next((p for p in all_pages() if p.group == group and p.name == name), None)
