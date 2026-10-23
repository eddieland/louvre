"""Louvre's web app: for now, the dummy deployment's pages over a sample artifact, with nothing stored.

An artifact's HTML is untrusted (REQUIREMENTS L7), so it is only ever served with a `sandbox` Content-Security-Policy:
the browser gives it an opaque origin of its own even when it is opened directly, so its scripts run but cannot read
Louvre's cookies or pages. The page that shows it frames it in an `<iframe sandbox>` without `allow-same-origin`, which
does the same from the other side.
"""

import html
from importlib.metadata import version
from importlib.resources import files

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from louvre.web import explorations

#: Where the pages and the sample artifact live, beside this module.
PAGES = files("louvre.web") / "pages"
#: The sample artifacts the demo serves, by id: the file each one's HTML is read from.
SAMPLES = {"checkout-latency": "sample-report.html"}
#: An artifact's own policy: an opaque origin, scripts and styles inline, images and fonts inline or from data URLs,
#: and no network. Whether an artifact may load from the network is an open question (REQUIREMENTS).
ARTIFACT_POLICY = (
    "sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox; "
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src data:; font-src data:; media-src data:"
)
#: Louvre's own pages: their own files only, and artifacts only in a frame from Louvre itself.
PAGE_POLICY = (
    "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; script-src 'self' 'unsafe-inline'; frame-src 'self'; frame-ancestors 'none'"
)
#: Headers every response carries: no guessing a type, and no referrer leaving with a link out of an artifact.
_NO_SNIFF = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}


def create() -> FastAPI:
    """Build the app.

    Returns:
        The ASGI app, which Vercel imports from `vercel_app.py` and `louvre serve` runs locally.
    """
    app = FastAPI(title="Louvre", version=version("louvre"), docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def landing() -> HTMLResponse:
        """The landing page."""
        return _page("landing.html")

    @app.get("/a/{artifact_id}", response_class=HTMLResponse)
    def viewer(artifact_id: str) -> HTMLResponse:
        """An artifact's page: Louvre's chrome around the artifact in a sandboxed frame."""
        _sample(artifact_id)
        return _page("viewer.html", artifact_id=artifact_id)

    @app.get("/a/{artifact_id}/content", response_class=HTMLResponse)
    def content(artifact_id: str) -> HTMLResponse:
        """An artifact's HTML, as its author wrote it, under the sandbox policy."""
        body = (PAGES / _sample(artifact_id)).read_text(encoding="utf-8")
        return HTMLResponse(body, headers={"Content-Security-Policy": ARTIFACT_POLICY, **_NO_SNIFF})

    @app.get("/directions", response_class=HTMLResponse)
    def directions() -> HTMLResponse:
        """The UI explorations, to open and compare."""
        items = "\n".join(
            f'        <a class="card" href="/directions/{html.escape(p.group)}/{html.escape(p.name)}">'
            f"<b>{html.escape(p.title)}</b><span>{html.escape(p.group)}</span></a>"
            for p in explorations.all_pages()
        )
        return _page("directions.html", trusted={"items": items or "        <p>No explorations here.</p>"})

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

    @app.get("/healthz")
    def health() -> dict[str, str]:
        """Liveness, with the version deployed."""
        return {"status": "ok", "version": version("louvre")}

    return app


def _sample(artifact_id: str) -> str:
    try:
        return SAMPLES[artifact_id]
    except KeyError:
        raise HTTPException(status_code=404, detail="No such artifact.") from None


def _page(name: str, *, trusted: dict[str, str] | None = None, **values: str) -> HTMLResponse:
    # `values` are escaped; `trusted` is HTML this module built from escaped pieces.
    body = (PAGES / name).read_text(encoding="utf-8")
    for key, value in values.items():
        body = body.replace("{{" + key + "}}", html.escape(value))
    for key, value in (trusted or {}).items():
        body = body.replace("{{" + key + "}}", value)
    return HTMLResponse(body, headers={"Content-Security-Policy": PAGE_POLICY, **_NO_SNIFF})
