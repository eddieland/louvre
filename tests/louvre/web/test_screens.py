"""Every page at every screen size, dark first (REQUIREMENTS U4): no sideways scroll, no page errors, and a screenshot.

The screenshots are checked in under docs/screenshots/, with a gallery, README.md, that lists them all. Two tests here
run in every test run, with no browser: each screenshot is checked in, and the gallery is current. The rest drive
Chromium, so they run only when asked: `make screens` checks every page at every size, as CI's screens job does, and
`make screenshots` also rewrites the screenshots and the gallery, for the diff to be reviewed with the change.
"""

import os
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import Browser, Page, sync_playwright

from louvre.web.app import create

#: The repository's root in a checkout.
ROOT = Path(__file__).resolve().parents[3]
#: Where the screenshots and their gallery are checked in.
SHOTS = ROOT / "docs" / "screenshots"
#: `1` drives the browser and checks every page; `update` also rewrites the screenshots and the gallery.
MODE = os.environ.get("LOUVRE_SCREENS", "")
#: How long a page may take to settle before the test fails, in seconds.
DEADLINE = 15.0


@dataclass(frozen=True)
class Screen:
    """A screen size and color scheme a page is held to."""

    #: The name the screenshot's file takes.
    name: str
    #: What the gallery calls it.
    label: str
    width: int
    height: int
    #: `dark`, the operator's (REQUIREMENTS U2), or `light`.
    scheme: str
    #: A phone or a tablet: touch, and a mobile viewport.
    touch: bool


@dataclass(frozen=True)
class Scene:
    """A page, in the state the screenshot shows it."""

    #: The name of the screenshot's directory.
    name: str
    #: What the gallery calls it.
    label: str
    path: str
    #: What to do on the page before it is checked, such as opening a thread.
    act: Callable[[Page], None] | None = None


def _open_thread(page: Page) -> None:
    page.click('mark[data-thread="t1"]')
    page.wait_for_selector('.thread[data-id="t1"].is-active', state="visible")


def _report_drawn(page: Page) -> None:
    page.frame_locator("iframe").locator("svg rect").first.wait_for()


#: Every screen, dark first; light at one phone and one laptop size.
SCREENS = (
    Screen("phone-small-dark", "Small phone, 360", 360, 780, "dark", touch=True),
    Screen("phone-dark", "Phone, 390", 390, 844, "dark", touch=True),
    Screen("tablet-dark", "Tablet, 820", 820, 1180, "dark", touch=True),
    Screen("tablet-landscape-dark", "Tablet landscape, 1180", 1180, 820, "dark", touch=True),
    Screen("laptop-dark", "Laptop, 1440", 1440, 900, "dark", touch=False),
    Screen("wide-dark", "Wide, 1920", 1920, 1080, "dark", touch=False),
    Screen("phone-light", "Phone, 390", 390, 844, "light", touch=True),
    Screen("laptop-light", "Laptop, 1440", 1440, 900, "light", touch=False),
)
#: Every page the web app serves, each in the state worth looking at.
SCENES = (
    Scene("landing", "Landing", "/"),
    Scene("artifact", "An artifact, sandboxed", "/a/checkout-latency", _report_drawn),
    Scene("directions", "Design directions", "/directions"),
    Scene("gallery", "Direction: Gallery, a thread open", "/directions/2026-10-23-directions/gallery", _open_thread),
    Scene("studio", "Direction: Studio, a thread open", "/directions/2026-10-23-directions/studio", _open_thread),
    Scene("margins", "Direction: Margins, a thread open", "/directions/2026-10-23-directions/margins", _open_thread),
)

browser_only = pytest.mark.skipif(MODE not in {"1", "update"}, reason="drives a browser: run `make screens`")


def test_every_screenshot_is_checked_in() -> None:
    if MODE == "update":
        pytest.skip("the screenshots are being written")
    missing = [_shot(scene, screen) for scene in SCENES for screen in SCREENS if not _shot(scene, screen).is_file()]
    assert not missing, "screenshots missing; run `make screenshots`:\n" + "\n".join(str(p) for p in missing)


def test_the_gallery_lists_every_screenshot() -> None:
    gallery = SHOTS / "README.md"
    if MODE == "update":
        gallery.parent.mkdir(parents=True, exist_ok=True)
        gallery.write_text(_gallery(), encoding="utf-8")
    assert gallery.read_text(encoding="utf-8") == _gallery(), "the gallery is stale; run `make screenshots`"


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    server = uvicorn.Server(uvicorn.Config(create(), host="127.0.0.1", port=0, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + DEADLINE
    while not server.started:
        assert time.monotonic() < deadline, "the web app did not start"
        time.sleep(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(DEADLINE)


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        # A Chromium of the machine's, where Playwright's own download is not to be had.
        executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE") or None
        launched = playwright.chromium.launch(executable_path=executable)
        yield launched
        launched.close()


@browser_only
@pytest.mark.parametrize("screen", SCREENS, ids=[s.name for s in SCREENS])
@pytest.mark.parametrize("scene", SCENES, ids=[s.name for s in SCENES])
def test_a_page_fits_the_screen(base_url: str, browser: Browser, scene: Scene, screen: Screen) -> None:
    context = browser.new_context(
        viewport={"width": screen.width, "height": screen.height},
        color_scheme="dark" if screen.scheme == "dark" else "light",
        is_mobile=screen.touch,
        has_touch=screen.touch,
        reduced_motion="reduce",
    )
    errors: list[str] = []
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    try:
        page.goto(base_url + scene.path, wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        if scene.act:
            scene.act(page)
        _settle(page)
        overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert overflow <= 0, f"{scene.name} scrolls sideways by {overflow}px on {screen.name}"
        assert not errors, f"{scene.name} on {screen.name}: " + "; ".join(errors)
        if MODE == "update":
            _shot(scene, screen).parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=_shot(scene, screen), animations="disabled", caret="hide")
    finally:
        context.close()


def _shot(scene: Scene, screen: Screen) -> Path:
    return SHOTS / scene.name / f"{screen.name}.png"


def _settle(page: Page) -> None:
    """Wait until the page has stopped scrolling, as a thread opened on a phone scrolls its passage into view."""
    page.wait_for_function(
        """() => {
            const settled = window.__lastScrollY === window.scrollY;
            window.__lastScrollY = window.scrollY;
            return settled;
        }""",
        polling=100,
        timeout=DEADLINE * 1000,
    )


def _gallery() -> str:
    narrow = [s for s in SCREENS if s.scheme == "dark" and s.width < 1000]
    wide = [s for s in SCREENS if s.scheme == "dark" and s.width >= 1000]
    light = [s for s in SCREENS if s.scheme == "light"]
    lines = [
        "# Screenshots",
        "",
        "Every page the web app serves, at every screen size it is held to, dark first, with light at a phone and a",
        "laptop (REQUIREMENTS U4). Generated by `make screenshots` from `tests/louvre/web/test_screens.py`, which also",
        "checks that no page scrolls sideways or logs an error at any size. Do not edit this file by hand.",
    ]
    for scene in SCENES:
        lines += ["", f"## {scene.label}", "", f"`{scene.path}`"]
        for title, screens in (("Narrow, dark", narrow), ("Wide, dark", wide), ("Light", light)):
            lines += ["", f"{title}:", "", "| " + " | ".join(s.label for s in screens) + " |"]
            lines += ["| " + " | ".join("---" for _ in screens) + " |"]
            cells = [f"![{scene.label}, {s.label}, {s.scheme}]({scene.name}/{s.name}.png)" for s in screens]
            lines += ["| " + " | ".join(cells) + " |"]
    return "\n".join(lines) + "\n"
