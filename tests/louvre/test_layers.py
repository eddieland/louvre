"""louvre's imports keep to its layers (AGENTS.md, Code conventions): only `louvre.cli` imports click, for now."""

import ast
from collections.abc import Iterator
from pathlib import Path

#: The repository's root in a checkout.
ROOT = Path(__file__).resolve().parents[2]
#: The package's source.
PACKAGE = ROOT / "src" / "louvre"
#: The one subpackage that may import click.
CLI = PACKAGE / "cli"


def test_only_the_cli_imports_click() -> None:
    found = [
        f"{path.relative_to(ROOT)}:{line}"
        for path in sorted(PACKAGE.rglob("*.py"))
        if not path.is_relative_to(CLI)
        for line, name in _imports(ast.parse(path.read_text(encoding="utf-8")))
        if name.partition(".")[0] == "click"
    ]
    assert not found, "click imported outside louvre.cli:\n" + "\n".join(found)


def test_the_check_finds_both_spellings_of_an_import() -> None:
    tree = ast.parse("import click.testing\nfrom click import echo\nimport rich\n")

    assert [name for _, name in _imports(tree)] == ["click.testing", "click", "rich"]


def _imports(tree: ast.Module) -> Iterator[tuple[int, str]]:
    for node in ast.walk(tree):
        match node:
            case ast.Import(names=names):
                for alias in names:
                    yield node.lineno, alias.name
            case ast.ImportFrom(module=str(module), level=0):
                yield node.lineno, module
            case _:
                pass
