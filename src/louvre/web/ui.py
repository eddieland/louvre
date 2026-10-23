"""The built web UI, ui/dist, which the app serves at its root, and the bridge it adds to artifacts' pages.

In a source checkout it sits at the repository root once `make ui-build` has run. In an installed wheel it is bundled
inside the package (`louvre/_data/ui`), built by the wheel's hook (hatch_build.py), which is how it reaches Vercel.
"""

from pathlib import Path

# This file is louvre/web/ui.py; bundled files sit beside the top-level package.
_PACKAGE = Path(__file__).resolve().parent.parent
_CANDIDATES = (_PACKAGE / "_data" / "ui", _PACKAGE.parent.parent / "ui" / "dist")


def dist() -> Path | None:
    """Find the built UI.

    Returns:
        Its directory, holding index.html, or None when this installation has none built.
    """
    return next((c for c in _CANDIDATES if (c / "index.html").is_file()), None)


def asset(root: Path, path: str) -> Path | None:
    """Find a built file by the path a URL names, never outside the build.

    Returns:
        The file, or None when there is none there, or the path leaves the build.
    """
    candidate = (root / path).resolve()
    if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
        return None
    return candidate


def bridge() -> str | None:
    """Read the built bridge, the script the app adds to every artifact's page (ui/src/bridge).

    Returns:
        Its JavaScript, or None when this installation has none built.
    """
    root = dist()
    found = None if root is None else root / "bridge" / "bridge.js"
    return found.read_text(encoding="utf-8") if found is not None and found.is_file() else None
