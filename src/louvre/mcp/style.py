"""Louvre's house style over MCP, beside `style_get`: its files as resources, and a prompt to write a page in it (U6).

A client lists the resources for a person to attach, as Claude Code's `@` does, and offers the prompt as a command, as
its `/mcp__louvre__style` does; a model that wants the style calls `style_get`. Each resource's URI names the style's
version, so a later style is new URIs beside these, and a page made from one never changes.
"""

from collections.abc import Mapping
from dataclasses import dataclass

import mcp_types as types
from mcp.shared.exceptions import MCPError

from louvre.core import style


@dataclass(frozen=True)
class File:
    """One of the style's files, as a resource."""

    uri: str
    name: str
    mime_type: str
    #: What it is, for the person or model choosing it.
    description: str
    text: str


#: The style's files, by URI.
FILES: Mapping[str, File] = {
    f.uri: f
    for f in (
        File(
            f"louvre://style/{style.VERSION}/style.css",
            f"{style.VERSION}.css",
            "text/css",
            "Louvre's house style: a stylesheet to inline in an HTML artifact's <style>, dark and light.",
            style.CSS,
        ),
        File(
            f"louvre://style/{style.VERSION}/rules.md",
            f"{style.VERSION} guide",
            "text/markdown",
            "How to use Louvre's house style: the page's shape, its components, charts, and writing for comments.",
            style.RULES,
        ),
        *(
            File(
                f"louvre://style/{style.VERSION}/starters/{kind}.html",
                f"{style.VERSION} {kind}",
                "text/html",
                f"An HTML page to start from, in Louvre's house style, for a {kind}. {about}",
                style.STARTERS[kind],
            )
            for kind, about in style.KINDS.items()
        ),
    )
}
#: The prompt's name, as a client offers it.
PROMPT = "style"
#: The prompt's argument: what the page is about.
ABOUT = "about"
#: The prompt's argument: the kind of artifact, which picks its starter page.
KIND = "kind"


def resources() -> list[types.Resource]:
    """List the style's files.

    Returns:
        Each file, as a resource.
    """
    return [
        types.Resource(
            uri=f.uri,
            name=f.name,
            mime_type=f.mime_type,
            description=f.description,
            size=len(f.text.encode()),
        )
        for f in FILES.values()
    ]


def read(uri: str) -> types.ReadResourceResult:
    """Read one of the style's files.

    Returns:
        Its text.

    Raises:
        MCPError: No file has that URI.
    """
    found = FILES.get(uri)
    if found is None:
        raise MCPError(types.INVALID_PARAMS, f"no resource {uri!r}")
    return types.ReadResourceResult(
        contents=[types.TextResourceContents(uri=found.uri, mime_type=found.mime_type, text=found.text)],
    )


def prompts() -> list[types.Prompt]:
    """List the prompt.

    Returns:
        The one prompt: write a page in the style.
    """
    return [
        types.Prompt(
            name=PROMPT,
            title="Write a page in Louvre's style",
            description=f"Write an HTML artifact in Louvre's house style, {style.VERSION}, and publish it.",
            arguments=[
                types.PromptArgument(name=ABOUT, description="What the page is about.", required=False),
                types.PromptArgument(
                    name=KIND,
                    description="The kind of artifact: " + ", ".join(style.Kind) + f"; {style.Kind.REPORT} if omitted.",
                    required=False,
                ),
            ],
        ),
    ]


def prompt(name: str, arguments: Mapping[str, str] | None) -> types.GetPromptResult:
    """Give the prompt, about what `arguments` say.

    Returns:
        One message from the person: the rules, and the starter page to write from.

    Raises:
        MCPError: No prompt has that name, or no kind of artifact the one asked for.
    """
    if name != PROMPT:
        raise MCPError(types.INVALID_PARAMS, f"no prompt {name!r}")
    about = (arguments or {}).get(ABOUT, "").strip()
    asked = (arguments or {}).get(KIND, "").strip() or style.Kind.REPORT
    try:
        kind = style.Kind(asked)
    except ValueError:
        raise MCPError(types.INVALID_PARAMS, f"no kind {asked!r}: " + ", ".join(style.Kind)) from None
    page = f"a {kind} about {about}" if about else f"the {kind} I ask for"
    text = (
        f"Write {page} as an HTML artifact in Louvre's house style, {style.VERSION}. Check it with style_check and "
        "fix what it finds, then publish it with artifact_publish, content_type text/html.\n\n"
        f"{style.RULES}\n"
        f"Start from this page, which inlines the stylesheet:\n\n```html\n{style.STARTERS[kind]}```\n"
    )
    return types.GetPromptResult(
        description=f"A page in Louvre's house style, {style.VERSION}.",
        messages=[types.PromptMessage(role="user", content=types.TextContent(type="text", text=text))],
    )
