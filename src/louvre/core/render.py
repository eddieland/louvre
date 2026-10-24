"""The page a version is shown as: its HTML, its Markdown in the house style, or its GeoJSON drawn as a map.

An HTML version is shown as its author wrote it, a Markdown one rendered in the house style, and GeoJSON as a map in
it (louvre.core.geodata).

Markdown is rendered by markdown-it-py with raw HTML off, so a Markdown version's source cannot put markup or a script
in its page: what looks like a tag is shown as text. Links keep markdown-it's own check, which refuses `javascript:` and
other script-bearing URLs.
"""

import html
from typing import assert_never

from markdown_it import MarkdownIt

from louvre.core import geodata, style
from louvre.core.text import ContentType, visible_text

#: CommonMark with GitHub's tables and strikethrough, and no raw HTML.
_MARKDOWN = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])


def page(content_type: ContentType, content: str, title: str) -> str:
    """Make the page a version is shown as.

    Returns:
        A whole HTML document: the content itself for `text/html`; for `text/markdown` the rendered source in the
        house style, under `title`; for GeoJSON, its map and its features.
    """
    match content_type:
        case "text/html":
            return content
        case "application/geo+json":
            return geodata.page(content, title)
        case "text/markdown":
            return _markdown(content, title)
        case _:
            assert_never(content_type)


def text_of(content_type: ContentType, content: str) -> str:
    """Read a version's text, which its anchors resolve against: what its page shows.

    Returns:
        The text, whitespace collapsed.
    """
    # The title is in <title>, which shows nothing, so any title gives the same text.
    return visible_text(page(content_type, content, ""))


def _markdown(content: str, title: str) -> str:
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n<style>\n{style.CSS}</style>\n</head>\n"
        f'<body class="louvre">\n<main>\n{_MARKDOWN.render(content)}</main>\n</body>\n</html>\n'
    )
