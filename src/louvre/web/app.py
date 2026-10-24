"""Louvre's web app: the web UI, its API, sign-in, artifacts' content in a sandbox, and the MCP server for agents.

An artifact's HTML is untrusted (REQUIREMENTS L7), so it is only ever served with a `sandbox` Content-Security-Policy:
the browser gives it an opaque origin of its own even when it is opened directly, so its scripts run but cannot read
Louvre's cookies or pages. The page that shows it frames it in an `<iframe sandbox>` without `allow-same-origin`, which
does the same from the other side. Louvre adds one script to it, the bridge (ui/src/bridge), which tells the page
where each thread's passage is and what the reader selected; it can do nothing the artifact's own scripts cannot.

A write through the API or sign-in needs the header `X-Louvre: 1`: a form or a link from another site cannot set it,
and a script from another site cannot send it without a preflight that Louvre never grants. Agents reach `/mcp` with a
token in `Authorization`, never a cookie.
"""

import html
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.metadata import version
from importlib.resources import files
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from mcp.server.context import ServerRequestContext
from starlette import types as asgi
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.routing import Route

from louvre.core import accounts, explorations, maps, style
from louvre.core import files as version_files
from louvre.core.store import Code, Refused, Scope, Store
from louvre.mcp import server
from louvre.web import api, auth, ui
from louvre.web.caller import Conn, Database, Reader
from louvre.web.settings import Settings

#: Where Louvre's own server-made pages live, beside this module.
PAGES = files("louvre.web") / "pages"
#: A version's file's own policy, opened alone: a sandbox, so an SVG runs no script, and nothing it may load.
FILE_POLICY = "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:"
#: The explorations' pages: their own files only, and fonts from Google, as the design study was made. Framed only by
#: Louvre, as the design study's board frames them.
PAGE_POLICY = (
    "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; script-src 'self' 'unsafe-inline'; frame-src 'self'; frame-ancestors 'self'"
)
#: The web UI's pages: its own scripts, styles, and fonts only, and artifacts only in a frame from Louvre itself.
APP_POLICY = (
    "default-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; "
    "frame-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)
#: The header a write must carry, and its value.
WRITE_HEADER = ("x-louvre", "1")
#: The status each refusal is answered with.
STATUS = {
    Code.NOT_FOUND: 404,
    Code.OUT_OF_SCOPE: 403,
    Code.TOO_LONG: 413,
    Code.ANCHOR_NOT_FOUND: 409,
    Code.READ_ONLY: 403,
    Code.INVALID: 422,
    Code.CLOSED: 409,
}
#: Headers every response carries: no guessing a type, and no referrer leaving with a link out of an artifact.
_NO_SNIFF = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}
#: Paths the web UI never answers, so a mistyped API route is a 404, not the UI's page.
_NOT_UI = ("api/", "auth/", "content/", "mcp", "directions", "style/", "kit/")


def create(settings: Settings | None = None) -> FastAPI:
    """Build the app, configured by `settings`, or by this process's environment.

    Returns:
        The ASGI app, which Vercel imports from `vercel_app.py` and `louvre serve` runs locally.
    """
    app = FastAPI(title="Louvre", version=version("louvre"), docs_url=None, redoc_url=None, openapi_url=None)
    app.state.database = Database(settings or Settings.from_environ())
    app.add_middleware(BaseHTTPMiddleware, dispatch=_writes_say_so)
    app.add_exception_handler(Refused, _refused)
    app.add_exception_handler(HTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _invalid)
    app.include_router(api.router)
    app.include_router(auth.router)

    _content(app)

    @app.get("/style/{version}/fonts/{name}", include_in_schema=False)
    def font(version: str, name: str) -> Response:
        """One of the house style's fonts, which an artifact's page loads from its opaque origin, so with CORS."""
        found = style.FONTS.get(name) if version == style.VERSION else None
        if found is None:
            raise HTTPException(status_code=404, detail="Not found.")
        return Response(
            found,
            media_type="font/woff2",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=31536000, immutable",
                **_NO_SNIFF,
            },
        )

    @app.get("/kit/{version}/{path:path}", include_in_schema=False)
    def kit(version: str, path: str) -> Response:
        """One of the map kit's files, which an artifact's page loads from its opaque origin, so with CORS."""
        found = maps.served(path) if version == maps.VERSION else None
        if found is None:
            raise HTTPException(status_code=404, detail="Not found.")
        media_type, data = found
        return Response(
            data,
            media_type=media_type,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=31536000, immutable",
                "Content-Security-Policy": FILE_POLICY,
                **_NO_SNIFF,
            },
        )

    # The MCP server, over streamable HTTP, for a request with a token: an ASGI app of the SDK's (louvre.mcp.server).
    app.router.routes.append(Route("/mcp", _Mcp(app.state.database), methods=["POST"]))

    @app.get("/mcp")
    def mcp_stream() -> Response:
        """No stream: the server sends nothing a client did not ask for, and a stream left open holds a function."""
        return Response(status_code=405, headers={"Allow": "POST"})

    _design_study(app)

    @app.get("/healthz")
    def health() -> dict[str, str]:
        """Liveness, with the version deployed."""
        return {"status": "ok", "version": version("louvre")}

    @app.get("/app", include_in_schema=False)
    @app.get("/app/{path:path}", include_in_schema=False)
    def old_app(path: str = "") -> RedirectResponse:
        """Where the web UI was before it took the root."""
        return RedirectResponse(f"/{path}", 308)

    # Last: every path no route above took is the web UI's.
    @app.get("/{path:path}", response_class=HTMLResponse, include_in_schema=False)
    def app_page(path: str = "") -> Response:
        """The web UI: a built file by its path, or the single page that routes every other path itself."""
        if path.startswith(_NOT_UI):
            raise HTTPException(status_code=404, detail="Not found.")
        return _app_response(path)

    return app


def artifact_policy(origin: str, files: str | None = None) -> str:
    """Make an artifact's own policy, as Louvre at `origin` serves it, beside its version's `files` if it has them.

    An opaque origin (D008); scripts and styles inline, and the map kit's script (louvre.core.maps), whose worker runs
    from a blob; images inline; fonts inline or the house style's, from Louvre (D008); the map kit's basemap and
    glyphs to read; the version's own files, under `files`, to load and read (D012); nothing else from the network;
    and framed only by Louvre. Whether an artifact may load from the network is an open question (REQUIREMENTS).

    Returns:
        The policy.
    """
    kit = f"{origin}{maps.PATH}"
    own = f" {origin}{files}" if files else ""
    return (
        "sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox; default-src 'none'; "
        f"script-src 'unsafe-inline' {kit}; worker-src blob:; style-src 'unsafe-inline'; img-src data: blob:{own}; "
        f"font-src data: 'self'{own}; media-src data:{own}; connect-src {kit}{own}; frame-ancestors 'self'"
    )


def _version_page(store: Store, artifact_id: str, n: int, policy: str) -> HTMLResponse:
    page = with_bridge(store.page(artifact_id, n), ui.bridge())
    return HTMLResponse(
        page,
        headers={"Content-Security-Policy": policy, "Cache-Control": "private, no-cache", **_NO_SNIFF},
    )


def with_bridge(page: str, bridge: str | None) -> str:
    """Add the bridge to a version's page, as a script at its end, which the page's text does not include.

    Returns:
        The page, or the page alone when the UI, and so the bridge, is not built.
    """
    if bridge is None:
        return page
    # A script's text ends at the first `</script`, whatever case, so the bridge must not hold one.
    safe = bridge.replace("</", "<\\/")
    return f"{page}\n<script>{safe}</script>\n"


def _origin(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _content(app: FastAPI) -> None:
    """Serve versions' pages, sandboxed (D008), and their files beside them (louvre.core.files)."""

    @app.get("/content/{artifact_id}/{n}", response_class=HTMLResponse)
    def content(request: Request, store: Reader, artifact_id: str, n: int) -> Response:
        """A version's page, as its author wrote it with the bridge added, under the sandbox policy.

        A version with files is served under its files' key instead, so the page names them relative to itself.
        """
        key = store.files_key(artifact_id, n)
        if key is not None:
            return RedirectResponse(f"/content/{artifact_id}/{n}/{key}/", 307, headers=_NO_SNIFF)
        return _version_page(store, artifact_id, n, artifact_policy(_origin(request)))

    @app.get("/content/{artifact_id}/{n}/{key}/", response_class=HTMLResponse)
    def content_with_files(request: Request, store: Reader, artifact_id: str, n: int, key: str) -> Response:
        """A version's page beside its files, under a policy that lets it load them, and nothing else."""
        if store.files_key(artifact_id, n) != key:
            raise HTTPException(status_code=404, detail="Not found.")
        here = f"/content/{artifact_id}/{n}/{key}/"
        return _version_page(store, artifact_id, n, artifact_policy(_origin(request), here))

    @app.get("/content/{artifact_id}/{n}/{key}/{path:path}", include_in_schema=False)
    def version_file(conn: Conn, artifact_id: str, n: int, key: str, path: str) -> Response:
        """One of a version's files, to whoever has its key (D012): a sandboxed page's request carries no session.

        CORS lets the page, on its opaque origin, load a font or read data from it.
        """
        found = version_files.served(conn, artifact_id, n, key, path)
        if found is None:
            raise HTTPException(status_code=404, detail="Not found.")
        content_type, data = found
        return Response(
            data,
            media_type=content_type.value,
            headers={
                "Content-Security-Policy": FILE_POLICY,
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "private, max-age=31536000, immutable",
                **_NO_SNIFF,
            },
        )


def _design_study(app: FastAPI) -> None:
    """Serve the design study (docs/ui-explorations), which the operator keeps to compare directions on a phone."""

    @app.get("/directions", response_class=HTMLResponse)
    def directions() -> HTMLResponse:
        """The design study, to open and compare."""
        items = "\n".join(
            f'        <a class="card" href="/directions/{html.escape(p.group)}/{html.escape(p.name)}">'
            f"<b>{html.escape(p.title)}</b><span>{html.escape(p.group)}</span></a>"
            for p in explorations.all_pages()
        )
        body = (PAGES / "directions.html").read_text(encoding="utf-8")
        board = (
            '        <a class="card" href="/directions/board">'
            "<b>The directions, as a board</b><span>pan, zoom, and open each</span></a>"
        )
        body = body.replace("{{items}}", f"{board}\n{items}" if items else "        <p>No explorations here.</p>")
        return HTMLResponse(body, headers={"Content-Security-Policy": PAGE_POLICY, **_NO_SNIFF})

    @app.get("/directions/board", include_in_schema=False)
    def directions_board() -> Response:
        """The design study as a board: a page of the web UI's, which needs no database (louvre.web.api)."""
        return _app_response("")

    @app.get("/directions/{group}/{name}", response_class=HTMLResponse)
    def direction(group: str, name: str) -> HTMLResponse:
        """One exploration's page, as it is in the repository."""
        page = explorations.find(group, name)
        if page is None:
            raise HTTPException(status_code=404, detail="No such exploration.")
        return HTMLResponse(
            page.path.read_text(encoding="utf-8"),
            headers={"Content-Security-Policy": PAGE_POLICY, **_NO_SNIFF},
        )


class _Mcp:
    """The MCP server, for a request whose token works, as that token's scope; any other is refused 401.

    An ASGI app, not a function, so the route hands it the request whole: the SDK answers it.
    """

    def __init__(self, found: Database) -> None:
        """Serve the MCP server over `found`, the app's database."""
        self.found = found
        self.app = server.http(server.server(self._open_store))

    async def __call__(self, scope: asgi.Scope, receive: asgi.Receive, send: asgi.Send) -> None:
        """Answer one request."""
        request = Request(scope)
        secret = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        token_scope = await run_in_threadpool(_token_scope, self.found, secret) if secret else None
        if token_scope is None:
            why = "the token is unknown or revoked" if secret else "a token is required: Authorization: Bearer lvt_..."
            await _unauthorized(why)(scope, receive, send)
            return
        request.state.token_scope = token_scope
        request.state.base_url = self.found.settings.base_url or str(request.base_url).rstrip("/")
        await self.app(scope, receive, send)

    @contextmanager
    def _open_store(self, ctx: ServerRequestContext[Any, Any]) -> Iterator[Store]:
        request = ctx.request
        assert isinstance(request, Request)  # noqa: S101  (the HTTP transport passes its request)
        with self.found.opened() as conn:
            yield Store(conn, request.state.token_scope, base_url=request.state.base_url)


def _token_scope(found: Database, secret: str) -> Scope | None:
    with found.opened() as conn:
        return accounts.token_scope(conn, secret)


def _unauthorized(message: str) -> JSONResponse:
    return JSONResponse(
        {"code": "unauthenticated", "message": message},
        status_code=401,
        headers={"WWW-Authenticate": 'Bearer realm="louvre"'},
    )


async def _writes_say_so(request: Request, call_next: RequestResponseEndpoint) -> Response:
    path = request.url.path
    if (
        request.method not in {"GET", "HEAD", "OPTIONS"}
        and path.startswith(("/api/", "/auth/"))
        and request.headers.get(WRITE_HEADER[0]) != WRITE_HEADER[1]
    ):
        return JSONResponse({"code": "forbidden", "message": "a write needs the header X-Louvre: 1"}, status_code=403)
    return await call_next(request)


async def _refused(_request: Request, error: Exception) -> Response:
    assert isinstance(error, Refused)  # noqa: S101  (registered for Refused)
    return JSONResponse({"code": error.code.value, "message": str(error)}, status_code=STATUS[error.code])


async def _http_error(_request: Request, error: Exception) -> Response:
    assert isinstance(error, HTTPException)  # noqa: S101  (registered for HTTPException)
    detail = error.detail
    body = detail if isinstance(detail, dict) else {"code": f"http_{error.status_code}", "message": str(detail)}
    return JSONResponse(body, status_code=error.status_code, headers=error.headers)


async def _invalid(_request: Request, error: Exception) -> Response:
    assert isinstance(error, RequestValidationError)  # noqa: S101  (registered for RequestValidationError)
    said = "; ".join(f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in error.errors())
    return JSONResponse({"code": "invalid", "message": said or "the request is not valid"}, status_code=422)


def _app_response(path: str) -> Response:
    root = ui.dist()
    if root is None:
        return HTMLResponse(
            "<!doctype html><title>Louvre</title><p>The web UI is not built: run <code>make ui-build</code>.</p>",
            status_code=503,
            headers={"Content-Security-Policy": APP_POLICY, **_NO_SNIFF},
        )
    found = ui.asset(root, path) if path else None
    if found is not None and found.name != "index.html":
        # Vite names every built asset by its content's hash, so a file under assets/ never changes.
        cache = "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
        return FileResponse(found, headers={"Cache-Control": cache, **_NO_SNIFF})
    return FileResponse(
        root / "index.html",
        media_type="text/html",
        headers={"Content-Security-Policy": APP_POLICY, "Cache-Control": "no-cache", **_NO_SNIFF},
    )
