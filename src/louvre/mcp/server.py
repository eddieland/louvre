"""Louvre's MCP server, on the MCP SDK's low-level server (D010): the SDK speaks the protocol, Louvre the tools.

The tools are canopy's definitions (louvre.mcp.tools), listed with their schemas as they are, and answered by the
store each call opens. Louvre's house style is resources and a prompt beside them (louvre.mcp.style), the same for
every token. A refusal, or arguments a tool's schema refuses, is a tool error, `isError`, whose text is one
JSON object, `{"code": ..., "message": ...}`. Over HTTP it runs stateless and answers in JSON: each request stands
alone, so any instance of the app answers any request, and no stream is left open.
"""

import json
import logging
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from importlib import metadata
from typing import Any

import anyio
import mcp_types as types
from mcp.server.context import ServerRequestContext
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from pydantic import ValidationError
from starlette.types import Receive, Scope, Send

from louvre.core.store import Code, Refused, Store
from louvre.mcp import style
from louvre.mcp.tools import TOOLS, Tool

#: The server's name, as `initialize` gives it.
NAME = "louvre"
#: What a client is told the server is for, when it connects: many put it in their model's instructions.
INSTRUCTIONS = (
    "Louvre hosts artifacts, pages people read and comment on: publish one with artifact_publish, read its threads "
    "with thread_list, and answer with comment_reply. Your token reaches one namespace. For an HTML page that looks "
    "like Louvre's own, call style_get with the kind of page, a report, a decision, or a plan: its stylesheet, its "
    "guide, and a starter page for each kind are resources too, and the style prompt writes a page in it. Before "
    "publishing an HTML page, check it with style_check."
)

#: Opens the store a call reaches, from the request's context: the token's scope, in a connection of its own.
type OpenStore = Callable[[ServerRequestContext[Any, Any]], AbstractContextManager[Store]]
#: An ASGI application.
type App = Callable[[Scope, Receive, Send], Any]

_log = logging.getLogger(__name__)


def server(open_store: OpenStore) -> Server[Any]:
    """Make the MCP server, whose tool calls reach the store `open_store` opens.

    Returns:
        The server.
    """

    async def list_tools(
        _ctx: ServerRequestContext[Any, Any],
        _params: types.PaginatedRequestParams | None,
    ) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[listed(t) for t in TOOLS])

    async def call_tool(
        ctx: ServerRequestContext[Any, Any],
        params: types.CallToolRequestParams,
    ) -> types.CallToolResult:
        found = next((t for t in TOOLS if t.name == params.name), None)
        if found is None:
            raise MCPError(types.INVALID_PARAMS, f"no tool named {params.name!r}")
        # The store is synchronous: it runs in a worker thread, as a synchronous route would.
        return await anyio.to_thread.run_sync(_call, found, params.arguments or {}, ctx, open_store)

    async def list_resources(
        _ctx: ServerRequestContext[Any, Any],
        _params: types.PaginatedRequestParams | None,
    ) -> types.ListResourcesResult:
        return types.ListResourcesResult(resources=style.resources())

    async def read_resource(
        _ctx: ServerRequestContext[Any, Any],
        params: types.ReadResourceRequestParams,
    ) -> types.ReadResourceResult:
        return style.read(params.uri)

    async def list_prompts(
        _ctx: ServerRequestContext[Any, Any],
        _params: types.PaginatedRequestParams | None,
    ) -> types.ListPromptsResult:
        return types.ListPromptsResult(prompts=style.prompts())

    async def get_prompt(
        _ctx: ServerRequestContext[Any, Any],
        params: types.GetPromptRequestParams,
    ) -> types.GetPromptResult:
        return style.prompt(params.name, params.arguments)

    return Server(
        NAME,
        version=metadata.version(NAME),
        instructions=INSTRUCTIONS,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
        on_list_resources=list_resources,
        on_read_resource=read_resource,
        on_list_prompts=list_prompts,
        on_get_prompt=get_prompt,
    )


def http(found: Server[Any]) -> App:
    """Serve `found` over streamable HTTP, stateless, each request answered in JSON.

    Returns:
        The ASGI app, which takes the request whatever its path.
    """
    # Every request carries a bearer token, never a cookie (D009), so a page another site serves gains nothing by
    # reaching it: the SDK's check of the Host and Origin headers, against DNS rebinding, is off.
    security = TransportSecuritySettings(enable_dns_rebinding_protection=False)

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        # A manager runs once and stops with its task group; one a request needs no app lifespan to start it.
        manager = StreamableHTTPSessionManager(found, json_response=True, stateless=True, security_settings=security)
        async with manager.run():
            await manager.handle_request(scope, receive, send)

    return app


def listed(found: Tool) -> types.Tool:
    """Describe a tool as `tools/list` lists it.

    Returns:
        Its name, description, and input schema, every reference inlined and no title, since some models' providers
        take no `$ref`, and a title only repeats its field's name.
    """
    whole = found.request.model_json_schema()
    # The request's docstring is for the store's readers; the tool's description says what it does.
    whole.pop("description", None)
    definitions = whole.pop("$defs", {})
    schema = _inlined(whole, definitions if isinstance(definitions, dict) else {})
    assert isinstance(schema, dict)  # noqa: S101  (a model's schema is an object)
    return types.Tool(name=found.name, description=found.description, input_schema=schema)


def _call(
    found: Tool,
    arguments: Mapping[str, object],
    ctx: ServerRequestContext[Any, Any],
    open_store: OpenStore,
) -> types.CallToolResult:
    try:
        with open_store(ctx) as store:
            return _said(found.call(arguments, store))
    except ValidationError as e:
        return _refused(Code.INVALID, _explain(e))
    except Refused as e:
        return _refused(e.code, str(e))
    except OverflowError:
        # Postgres's integers are 64 bits; a JSON number need not be.
        return _refused(Code.INVALID, "a number is past the most the store holds")


def _explain(error: ValidationError) -> str:
    """Say what is wrong with arguments, without echoing them: a value may be a whole page.

    Returns:
        Each problem, `where: what`, joined by semicolons.
    """
    return "; ".join(
        f"{'.'.join(str(at) for at in problem['loc']) or 'arguments'}: {problem['msg']}" for problem in error.errors()
    )


def _said(text: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=False)


def _refused(code: Code, message: str) -> types.CallToolResult:
    text = json.dumps({"code": code.value, "message": message}, ensure_ascii=False)
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=True)


def _inlined(node: object, definitions: Mapping[str, object], *, fields: bool = False) -> object:
    """Inline each `$ref` in `node`, and leave out each schema's `title`.

    `fields` marks a `properties` object, whose keys are field names, kept whatever they are.

    Returns:
        `node` with each reference replaced by the definition it names.
    """
    if isinstance(node, list):
        return [_inlined(item, definitions) for item in node]
    if not isinstance(node, dict):
        return node
    if fields:
        return {name: _inlined(value, definitions) for name, value in node.items()}
    ref = node.get("$ref")
    if isinstance(ref, str):
        # A definition's description is its class's docstring; a field's own is kept.
        named = definitions.get(ref.rsplit("/", 1)[-1])
        defined = {k: v for k, v in named.items() if k != "description"} if isinstance(named, dict) else {}
        return _inlined({**defined, **{k: v for k, v in node.items() if k != "$ref"}}, definitions)
    return {
        key: _inlined(value, definitions, fields=key == "properties") for key, value in node.items() if key != "title"
    }
