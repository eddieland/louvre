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
from importlib.metadata import version
from importlib.resources import files
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from louvre.core import accounts
from louvre.core.store import Code, Refused, Store
from louvre.mcp import server
from louvre.web import api, auth, explorations, ui
from louvre.web.caller import NOT_CONFIGURED, Database, Reader, database
from louvre.web.settings import Settings

#: Where Louvre's own server-made pages live, beside this module.
PAGES = files("louvre.web") / "pages"
#: An artifact's own policy: an opaque origin, scripts and styles inline, images and fonts inline or from data URLs,
#: no network, and framed only by Louvre. Whether an artifact may load from the network is an open question
#: (REQUIREMENTS).
ARTIFACT_POLICY = (
    "sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox; "
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src data:; font-src data:; media-src data:; frame-ancestors 'self'"
)
#: The explorations' pages: their own files only, and fonts from Google, as the design study was made.
PAGE_POLICY = (
    "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; script-src 'self' 'unsafe-inline'; frame-src 'self'; frame-ancestors 'none'"
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
}
#: Headers every response carries: no guessing a type, and no referrer leaving with a link out of an artifact.
_NO_SNIFF = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}
#: Paths the web UI never answers, so a mistyped API route is a 404, not the UI's page.
_NOT_UI = ("api/", "auth/", "content/", "mcp", "directions")


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

    @app.get("/content/{artifact_id}/{n}", response_class=HTMLResponse)
    def content(store: Reader, artifact_id: str, n: int) -> HTMLResponse:
        """A version's page, as its author wrote it with the bridge added, under the sandbox policy."""
        page = with_bridge(store.page(artifact_id, n), ui.bridge())
        return HTMLResponse(
            page,
            headers={"Content-Security-Policy": ARTIFACT_POLICY, "Cache-Control": "private, no-cache", **_NO_SNIFF},
        )

    @app.post("/mcp")
    async def mcp(request: Request, found: Annotated[Database, Depends(database)]) -> Response:
        """The MCP server, over streamable HTTP: one JSON-RPC message a request, answered as JSON."""
        body = await request.body()
        # The store is synchronous: it runs in a worker thread, as a synchronous route would.
        return await run_in_threadpool(_mcp, request, found, body)

    @app.get("/mcp")
    def mcp_stream() -> Response:
        """No stream: the server sends nothing a client did not ask for."""
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
        body = body.replace("{{items}}", items or "        <p>No explorations here.</p>")
        return HTMLResponse(body, headers={"Content-Security-Policy": PAGE_POLICY, **_NO_SNIFF})

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


def _mcp(request: Request, found: Database, body: bytes) -> Response:
    secret = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not secret:
        return _unauthorized("a token is required: Authorization: Bearer lvt_...")
    with found.opened() as held:
        if held.conn is None:
            # A token is a row of the database: without one, no agent is known.
            return JSONResponse({"code": "not_configured", "message": NOT_CONFIGURED}, status_code=503)
        scope = accounts.token_scope(held.conn, secret)
        if scope is None:
            return _unauthorized("the token is unknown or revoked")
        base_url = found.settings.base_url or str(request.base_url).rstrip("/")
        answered = server.answer(body, Store(held.tables, scope, base_url=base_url))
    if answered is None:
        return Response(status_code=202)
    return JSONResponse(answered)


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
