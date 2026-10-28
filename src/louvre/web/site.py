"""A deployment's own words: its name, and what its owner says on Louvre's pages (docs/DEPLOY.md).

An organization that runs Louvre says what is its own on its pages: a banner over every page (whose deployment this
is, what may be posted to it), a footer (where to ask for help, its policies), a note where people sign in (who may,
and how to ask), and one where they mint tokens (its conventions for agents). Each is Markdown, of which Louvre keeps
paragraphs, line breaks, emphasis, code, and links, and sends the page those as runs of text, never as HTML: the page
draws them as text, so nothing the owner writes runs as markup or a script on the origin that holds a person's
session (REQUIREMENTS L7). A link goes only to the web, an address, or a path of Louvre's own.
"""

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Self

from markdown_it import MarkdownIt
from markdown_it.token import Token

#: Inline Markdown only, with no raw HTML: what looks like a tag, a heading, or a list is shown as its text.
_MARKDOWN = MarkdownIt("zero", {"html": False}).enable(["emphasis", "link", "backticks", "escape", "entity", "newline"])
#: The schemes a link may take; any other link is shown as its text alone. A path of Louvre's own is allowed beside.
_SCHEMES = ("https://", "http://", "mailto:")

#: One run of text, as the page draws it: its `text`, with `href` for a link, and `strong`, `em`, or `code` when set.
type Run = dict[str, str | bool]
#: A paragraph, as runs of text; a line break is a newline in one.
type Paragraph = list[Run]


@dataclass(frozen=True)
class Site:
    """What a deployment's owner says on its pages, each as Markdown, and empty for nothing."""

    #: What the deployment is called, such as `Acme Louvre`, in each page's title; empty for Louvre.
    name: str = ""
    #: Above the header of every page, such as whose deployment this is.
    banner: str = ""
    #: At the foot of the pages that list things, and of signing in, such as where to ask for help.
    footer: str = ""
    #: Where a person signs in, such as who may and how to ask for access.
    sign_in: str = ""
    #: On the Tokens page, such as the deployment's conventions for agents and their namespaces.
    tokens: str = ""

    @classmethod
    def from_environ(cls, environ: Mapping[str, str] | None = None) -> Self:
        """Read the owner's words from `environ`, this process's environment unless given.

        Returns:
            The words, each empty when its variable is unset.
        """
        env = os.environ if environ is None else environ
        return cls(
            name=" ".join(env.get("LOUVRE_NAME", "").split()),
            banner=env.get("LOUVRE_BANNER", "").strip(),
            footer=env.get("LOUVRE_FOOTER", "").strip(),
            sign_in=env.get("LOUVRE_SIGN_IN_NOTE", "").strip(),
            tokens=env.get("LOUVRE_TOKENS_NOTE", "").strip(),
        )

    def shown(self) -> dict[str, object]:
        """Say what the pages show, as the session gives it to the web UI.

        Returns:
            The name, and each of the owner's notes as paragraphs of runs, none for a note left empty.
        """
        return {
            "name": self.name,
            "banner": paragraphs(self.banner),
            "footer": paragraphs(self.footer),
            "sign_in": paragraphs(self.sign_in),
            "tokens": paragraphs(self.tokens),
        }


def paragraphs(markdown: str) -> list[Paragraph]:
    """Read inline Markdown as paragraphs of runs of text, which the page draws as text.

    A blank line starts a paragraph, and a new line breaks one, as a comment on GitHub does.

    Returns:
        The paragraphs, each a list of runs, adjacent runs alike merged; none for blank Markdown.
    """
    found: list[Paragraph] = []
    for token in _MARKDOWN.parse(markdown):
        if token.type == "inline":
            runs = _runs(token.children or [])
            if runs:
                found.append(runs)
    return found


def _runs(children: Sequence[Token]) -> Paragraph:
    runs: Paragraph = []
    strong = em = 0
    href = ""
    for child in children:
        match child.type:
            case "strong_open" | "strong_close":
                strong += 1 if child.nesting > 0 else -1
            case "em_open" | "em_close":
                em += 1 if child.nesting > 0 else -1
            case "link_open":
                href = _safe(str(child.attrGet("href") or ""))
            case "link_close":
                href = ""
            case "text":
                _add(runs, {"text": child.content, "href": href, "strong": strong > 0, "em": em > 0})
            case "code_inline":
                _add(runs, {"text": child.content, "href": href, "code": True})
            case "softbreak" | "hardbreak":
                _add(runs, {"text": "\n", "href": href})
            case _:
                # Nothing else is enabled: raw HTML and images are off, so they never come.
                pass
    return runs


def _safe(href: str) -> str:
    """Keep a link to the web, an address, or a path of Louvre's own; anything else, `javascript:` say, is dropped."""
    # `//host` and `/\host` are another site's, as a browser reads them.
    own = href.startswith("/") and href[1:2] not in {"/", "\\"}
    return href if own or href.lower().startswith(_SCHEMES) else ""


def _add(runs: Paragraph, run: Run) -> None:
    """Add `run`, its falsy marks left out, to the end of `runs`: to the last run's text when its marks are the same."""
    marks = {key: value for key, value in run.items() if value}
    text = marks.pop("text", "")
    if not text:
        return
    if runs and {key: value for key, value in runs[-1].items() if key != "text"} == marks:
        runs[-1]["text"] = f"{runs[-1]['text']}{text}"
    else:
        runs.append({"text": text, **marks})
