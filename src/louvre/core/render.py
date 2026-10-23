"""The page a version is shown as: an HTML version as its author wrote it, a Markdown one rendered in the house style.

Markdown is rendered by markdown-it-py with raw HTML off, so a Markdown version's source cannot put markup or a script
in its page: what looks like a tag is shown as text. Links keep markdown-it's own check, which refuses `javascript:` and
other script-bearing URLs.
"""

import html

from markdown_it import MarkdownIt

from louvre.core import style
from louvre.core.text import ContentType, visible_text

#: CommonMark with GitHub's tables and strikethrough, and no raw HTML.
_MARKDOWN = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])


def page(content_type: ContentType, content: str, title: str) -> str:
    """Make the page a version is shown as.

    Returns:
        A whole HTML document: the content itself for `text/html`, or for `text/markdown` the rendered source in the
        house style, under `title`.
    """
    if content_type == "text/html":
        return content
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n<style>\n{style.CSS}</style>\n</head>\n"
        f'<body class="louvre">\n<main>\n{_MARKDOWN.render(content)}</main>\n</body>\n</html>\n'
    )


def text_of(content_type: ContentType, content: str) -> str:
    """Read a version's text, which its anchors resolve against: what its page shows.

    Returns:
        The text, whitespace collapsed.
    """
    # The title is in <title>, which shows nothing, so any title gives the same text.
    return visible_text(page(content_type, content, ""))
