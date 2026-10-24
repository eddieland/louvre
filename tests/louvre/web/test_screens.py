"""Every page at every screen size, dark first (REQUIREMENTS U4): no sideways scroll, no page errors, and a screenshot.

The screenshots are checked in under docs/screenshots/, with a gallery, README.md, that lists them all. Two tests here
run in every test run, with no browser: each screenshot is checked in, and the gallery is current. The rest drive
Chromium, so they run only when asked: `make screens` checks every page at every size, as CI's screens job does, and
`make screenshots` also rewrites the screenshots and the gallery, for the diff to be reviewed with the change.
"""

import json
import os
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page

from tests.conftest import WRITES

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
    #: The page's path; `{checkout}`, `{notes}`, `{weekly}`, and `{gallery}` stand for the demo's artifacts' ids.
    path: str
    #: What to do on the page before it is checked, such as opening a thread.
    act: Callable[[Page], None] | None = None
    #: Whether the reader is signed in, as Ana, or reads the demo without signing in.
    signed_in: bool = True


def _open_thread(page: Page) -> None:
    page.click('mark[data-thread="t1"]')
    page.wait_for_selector('.thread[data-id="t1"].is-active', state="visible")


def _artifact_shown(page: Page) -> None:
    """Wait until the bridge has marked the artifact's passages and the margin has placed their threads."""
    page.frame_locator("iframe.exhibit").locator("[data-louvre] span").first.wait_for()
    page.wait_for_function("document.querySelector('iframe.exhibit').offsetHeight > 480")


def _board_shown(page: Page) -> None:
    """Wait until the board is fitted to the screen and every frame's page has loaded."""
    page.wait_for_selector(".world[data-ready]", state="attached")
    page.wait_for_function("document.querySelectorAll('.board-frame iframe').length === 6")
    for frame in page.frames[1:]:
        frame.wait_for_load_state("load")


def _report_open(page: Page) -> None:
    """The report drawn, and its first thread open."""
    _artifact_shown(page)
    page.frame_locator("iframe.exhibit").locator("svg rect").first.wait_for()
    page.keyboard.press("j")
    page.wait_for_selector(".thread.is-active", state="visible")


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
    Scene("catalogue", "The catalogue, signed in", "/"),
    Scene("reader", "The catalogue, reading the demo without signing in", "/", signed_in=False),
    Scene("sign-in", "Signing in", "/sign-in", signed_in=False),
    Scene("artifact", "An artifact, a thread open", "/a/{checkout}", _report_open),
    Scene("artifact-older", "An artifact's older version", "/a/{checkout}?v=1", _artifact_shown),
    Scene("markdown", "A Markdown artifact, in the house style", "/a/{notes}", _artifact_shown),
    Scene("house-style", "An HTML artifact in the house style", "/a/{weekly}", _artifact_shown),
    Scene("board", "A board, fitted to the screen", "/b/design-study", _board_shown),
    Scene(
        "board-frame",
        "A board's frame, opened at its size",
        "/a/{gallery}?board=design-study&frame=gallery-phone",
        _artifact_shown,
    ),
    Scene("tokens", "Tokens", "/tokens"),
    Scene("directions", "Design directions", "/directions"),
    Scene("directions-board", "Design directions, as a board", "/directions/board", _board_shown, signed_in=False),
    Scene("gallery", "Direction: Gallery, a thread open", "/directions/2026-10-23-directions/gallery", _open_thread),
    Scene("studio", "Direction: Studio, a thread open", "/directions/2026-10-23-directions/studio", _open_thread),
    Scene("margins", "Direction: Margins, a thread open", "/directions/2026-10-23-directions/margins", _open_thread),
    Scene("annotated", "Blend: Annotated, a thread open", "/directions/2026-10-23-blends/annotated", _open_thread),
    Scene("open", "Blend: Open, a thread open", "/directions/2026-10-23-blends/open", _open_thread),
)
#: The demo's artifacts, by the name a scene's path gives each, and how its title starts.
DEMO = {
    "checkout": "Checkout latency",
    "notes": "Release notes",
    "weekly": "Payments, week",
    "gallery": "Direction: Gallery",
}

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
def demo(live_app: str) -> dict[str, str]:
    """The demo's artifacts' ids, by the names scenes' paths give them."""
    with urllib.request.urlopen(f"{live_app}/api/artifacts") as response:  # noqa: S310  (the test's own server)
        listed = json.load(response)["artifacts"]
    return {name: next(a["id"] for a in listed if a["title"].startswith(t)) for name, t in DEMO.items()}


@browser_only
@pytest.mark.parametrize("screen", SCREENS, ids=[s.name for s in SCREENS])
@pytest.mark.parametrize("scene", SCENES, ids=[s.name for s in SCENES])
def test_a_page_fits_the_screen(
    live_app: str,
    demo: Mapping[str, str],
    browser: Browser,
    scene: Scene,
    screen: Screen,
) -> None:
    context = browser.new_context(
        viewport={"width": screen.width, "height": screen.height},
        color_scheme="dark" if screen.scheme == "dark" else "light",
        is_mobile=screen.touch,
        has_touch=screen.touch,
        reduced_motion="reduce",
    )
    if scene.signed_in:
        signed = context.request.post(f"{live_app}/auth/dev", data={"login": "ana", "name": "Ana Ruiz"}, headers=WRITES)
        assert signed.status == 204
    errors: list[str] = []
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    try:
        page.goto(live_app + scene.path.format_map(demo), wait_until="networkidle")
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
