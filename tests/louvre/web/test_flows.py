"""What people do on Louvre's pages, in Chromium: comment on selected words, reply, resolve, pan a board, mint tokens.

These drive a browser, so they run with the screen matrix (`make screens`, CI's screens job), against the live app on
the test database. A selection is made inside the artifact's sandboxed frame, as a reader's would be, so the bridge's
reading of the page and the server's must agree for a comment to land.
"""

import json
import os
import re
import time
from collections.abc import Iterator, Sequence

import pytest
from playwright.sync_api import Browser, BrowserContext, CDPSession, ConsoleMessage, Page, expect

from louvre.core import style
from tests.conftest import WRITES

#: Run with the screen matrix: `1` or `update`.
MODE = os.environ.get("LOUVRE_SCREENS", "")
#: A page an agent publishes: a passage that crosses an inline tag, and one that crosses a block.
PAGE = (
    "<!doctype html><html><head><title>Cache report</title></head><body><main>"
    "<h1>Cache report</h1><p>The cache is <em>slow under load</em>, because every miss takes the lock.</p>"
    "<p>We should shard it.</p><p>Then measure again.</p></main></body></html>"
)

#: Two PNGs, one pixel wide and two, base64-encoded as an agent publishes them.
ONE_WIDE = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGNgAAIAAAUAAXpeqz8AAAAASUVORK5CYII="
TWO_WIDE = "iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAYAAAD0In+KAAAAC0lEQVR4nGNggAIAAAkAAftSuKkAAAAASUVORK5CYII="
#: How close two of a board's views are to be the same: the browser keeps a transform to a few decimal places.
CLOSE = 0.001
#: How long a board may take to be drawn as a test expects, in seconds.
DEADLINE = 5.0
#: The board's least zoom (ui/src/lib/canvas.ts, MIN_SCALE).
MIN_SCALE = 0.05
#: How many frames' pages a phone draws live at most (ui/src/lib/canvas.ts, LIVE_COUNT).
LIVE_COUNT = 2
#: How far past its frame a frame's shadows may reach on the canvas, in canvas pixels: the sheet's shadow's reach.
SHADOW_REACH = 48

pytestmark = pytest.mark.skipif(MODE not in {"1", "update"}, reason="drives a browser: run `make screens`")


@pytest.fixture
def context(browser: Browser, live_app: str) -> Iterator[BrowserContext]:
    """A browser signed in as Ana, at a laptop's size."""
    made = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark", base_url=live_app)
    signed = made.request.post("/auth/dev", data={"login": "ana", "name": "Ana Ruiz"}, headers=WRITES)
    assert signed.status == 204
    yield made
    made.close()


def publish(context: BrowserContext, content: str = PAGE) -> str:
    """Publish `content` as Ana's agent, through the MCP server with a token she mints, and return its id."""
    minted = context.request.post(
        "/api/tokens",
        data={"name": "canopy worker", "namespace": "canopy/ana", "scopes": ["read", "publish", "comment"]},
        headers=WRITES,
    ).json()
    called = context.request.post(
        "/mcp",
        data={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "artifact_publish",
                "arguments": {"title": "Cache report", "content_type": "text/html", "content": content},
            },
        },
        headers={"Authorization": f"Bearer {minted['secret']}"},
    ).json()
    artifact = json.loads(called["result"]["content"][0]["text"])["artifact_id"]
    context.request.post(
        "/mcp",
        data={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "comment_create",
                "arguments": {
                    "artifact_id": artifact,
                    "anchor": {"exact": "We should shard it."},
                    "body": "Sharding is the fix I would try first.",
                },
            },
        },
        headers={"Authorization": f"Bearer {minted['secret']}"},
    )
    return str(artifact)


def shown(page: Page) -> None:
    """Wait until the bridge has marked the page's passages."""
    page.frame_locator("iframe.exhibit").locator("[data-louvre] span").first.wait_for()


def select(page: Page, start: str, end: str) -> None:
    """Select, inside the frame, from the first character of `start` to the last of `end`."""
    frame = next(f for f in page.frames if "/content/" in f.url)
    frame.evaluate(
        """([start, end]) => {
            const find = (words) => {
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                while (walker.nextNode()) {
                    const at = walker.currentNode.data.indexOf(words);
                    if (at >= 0) return [walker.currentNode, at];
                }
                throw new Error(`no ${words}`);
            };
            const [from, i] = find(start);
            const [to, j] = find(end);
            const range = document.createRange();
            range.setStart(from, i);
            range.setEnd(to, j + end.length);
            getSelection().removeAllRanges();
            getSelection().addRange(range);
        }""",
        [start, end],
    )


def test_an_agents_page_shows_its_comment_on_its_passage(context: BrowserContext) -> None:
    page = context.new_page()
    page.goto(f"/a/{publish(context)}")
    shown(page)

    note = page.locator(".rail > .thread").first
    expect(note).to_contain_text("Sharding is the fix I would try first.")
    expect(note).to_contain_text("(Agent, for Ana Ruiz)")
    expect(page.frame_locator("iframe.exhibit").locator("[data-louvre] span")).to_have_text("1")


def test_each_version_shows_its_own_files_from_its_sandbox(context: BrowserContext) -> None:
    secret = context.request.post(
        "/api/tokens",
        data={"name": "canopy worker", "namespace": "canopy/ana", "scopes": ["read", "publish"]},
        headers=WRITES,
    ).json()["secret"]

    def publish_chart(data: str, artifact_id: str | None = None) -> str:
        arguments = {
            "title": "Chart",
            "content_type": "text/html",
            "content": '<!doctype html><h1>Chart</h1><img id="chart" src="chart.png" alt="A chart">',
            "files": [{"path": "chart.png", "content_type": "image/png", "data": data}],
            **({"artifact_id": artifact_id} if artifact_id else {}),
        }
        answered = context.request.post(
            "/mcp",
            data={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "files_publish", "arguments": arguments},
            },
            headers={"Authorization": f"Bearer {secret}"},
        ).json()
        return str(json.loads(answered["result"]["content"][0]["text"])["artifact_id"])

    artifact = publish_chart(ONE_WIDE)
    publish_chart(TWO_WIDE, artifact)

    def width(version: int) -> int:
        page = context.new_page()
        page.goto(f"/a/{artifact}?v={version}")
        exhibit = page.locator("iframe.exhibit").element_handle()
        frame = exhibit.content_frame() if exhibit else None
        assert frame is not None
        frame.wait_for_load_state()
        # The frame's request for the image carries no session: the version's key in its path is what it needs.
        return int(frame.evaluate("document.getElementById('chart').naturalWidth"))

    assert width(1) == 1
    assert width(2) == 2


def test_a_page_in_the_house_style_is_set_in_louvres_own_faces(context: BrowserContext) -> None:
    page = context.new_page()
    page.goto(f"/a/{publish(context, style.STARTERS[style.Kind.REPORT])}")
    exhibit = page.locator("iframe.exhibit").element_handle()
    frame = exhibit.content_frame() if exhibit else None
    assert frame is not None
    frame.wait_for_load_state()

    loaded = frame.evaluate(
        """async () => {
            await document.fonts.ready;
            return [...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family.replaceAll('"', ""));
        }""",
    )
    assert {"Fraunces", "Source Serif 4", "Instrument Sans"} <= set(loaded)


def test_a_map_is_drawn_in_its_sandbox_from_the_kit_louvre_serves(context: BrowserContext) -> None:
    page = context.new_page()
    refused: list[str] = []

    def heard(message: ConsoleMessage) -> None:
        if "Content Security Policy" in message.text:
            refused.append(message.text)

    page.on("console", heard)
    page.goto(f"/a/{publish(context, style.STARTERS[style.Kind.MAP])}")
    frame = page.frame_locator("iframe.exhibit")

    expect(frame.locator("#map[data-drawn]")).to_be_attached(timeout=DEADLINE * 1000 * 3)
    expect(frame.locator("#map canvas")).to_be_visible()
    assert not refused


def test_a_vehicles_trace_is_drawn_at_a_streets_scale_on_its_streets_and_named_once(context: BrowserContext) -> None:
    def street(*cells: tuple[int, int]) -> list[list[float]]:
        return [[-9.145 + 0.0016 * i, 38.71 + 0.0012 * j] for i, j in cells]

    streets = [street((i, 0), (i, 4)) for i in range(5)] + [street((0, j), (4, j)) for j in range(5)]
    trace = {"type": "MultiLineString", "coordinates": [street((0, 1), (2, 1), (2, 3)), street((3, 0), (3, 2))]}
    data = {"type": "Feature", "properties": {"name": "Van 7", "mark": 1}, "geometry": trace}
    context_ = {"type": "MultiLineString", "coordinates": streets}
    starter = style.STARTERS[style.Kind.MAP]
    start = starter.index('LouvreMap.draw("map", {')
    drawn = f'LouvreMap.draw("map", {{ data: {json.dumps(data)}, context: {json.dumps(context_)} }});\n'
    page = context.new_page()
    page.goto(f"/a/{publish(context, starter[:start] + drawn + starter[starter.index('</script>', start) :])}")
    frame = page.frame_locator("iframe.exhibit")

    expect(frame.locator("#map[data-drawn]")).to_be_attached(timeout=DEADLINE * 1000)
    shown = frame.locator("#map").evaluate(
        """(element) => {
            const map = element.louvreMap;
            const named = map.queryRenderedFeatures({ layers: ["labels"] }).map((f) => f.properties["louvre:label"]);
            return { zoom: map.getZoom(), named };
        }""",
    )
    # A few streets fill the map, and the trace in two parts is named once.
    assert shown["zoom"] > 14
    assert shown["named"] == ["Van 7"]


def test_on_a_phone_a_page_keeps_one_map_drawn_the_one_in_view(browser: Browser, live_app: str) -> None:
    phone = browser.new_context(
        viewport={"width": 390, "height": 844},
        is_mobile=True,
        has_touch=True,
        base_url=live_app,
    )
    assert phone.request.post("/auth/dev", data={"login": "ana", "name": "Ana Ruiz"}, headers=WRITES).status == 204
    starter = style.STARTERS[style.Kind.MAP]
    second = '<div style="height: 150vh"></div><div class="l-map" id="second"></div>'
    twice = starter.replace("<h2>Each place", f"{second}<h2>Each place").replace(
        "</script>\n</body>",
        'LouvreMap.draw("second", {});\n</script>\n</body>',
    )
    page = phone.new_page()
    page.goto(f"/a/{publish(phone, twice)}")
    frame = page.frame_locator("iframe.exhibit")

    frame.locator("#map").scroll_into_view_if_needed()
    expect(frame.locator("#map[data-drawn]")).to_be_attached(timeout=DEADLINE * 1000)
    expect(frame.locator("#second canvas")).to_have_count(0)
    frame.locator("#second").scroll_into_view_if_needed()
    expect(frame.locator("#second[data-drawn]")).to_be_attached(timeout=DEADLINE * 1000)
    expect(frame.locator("#map canvas")).to_have_count(0)
    phone.close()


def test_a_reader_comments_on_words_across_tags_then_replies_resolves_and_undoes(context: BrowserContext) -> None:
    artifact = publish(context)
    page = context.new_page()
    page.goto(f"/a/{artifact}")
    shown(page)

    select(page, "cache is", "load")
    page.click("button.add")
    page.fill(".thread[data-id=draft] textarea", "Under what load?")
    page.keyboard.press("Control+Enter")
    expect(page.locator(".thread.is-active .comments")).to_contain_text("Under what load?")

    threads = context.request.get(f"/api/artifacts/{artifact}/threads").json()["threads"]
    [mine] = [t for t in threads if t["comments"][0]["body"] == "Under what load?"]
    assert mine["anchor"]["exact"] == "cache is slow under load"
    assert mine["anchor"]["prefix"] == "Cache report The"

    page.fill(".thread.is-active textarea", "Peak, I mean.")
    page.click(".thread.is-active button:text-is('Reply')")
    expect(page.locator(".thread.is-active")).to_contain_text("Peak, I mean.")

    page.click(".thread.is-active button:text-is('Resolve')")
    expect(page.locator(".toast")).to_contain_text("Thread resolved")
    page.click(".toast button:text-is('Undo')")
    expect(page.get_by_role("button", name=re.compile(r"^Open 2$"))).to_be_visible()


def test_a_selection_across_blocks_comments_too(context: BrowserContext) -> None:
    artifact = publish(context)
    page = context.new_page()
    page.goto(f"/a/{artifact}")
    shown(page)

    select(page, "shard it", "Then measure")
    expect(page.locator("button.add")).to_be_visible()
    page.keyboard.press("c")
    page.fill(".thread[data-id=draft] textarea", "Both, please.")
    page.keyboard.press("Control+Enter")

    expect(page.locator(".thread.is-active .comments")).to_contain_text("Both, please.")
    threads = context.request.get(f"/api/artifacts/{artifact}/threads").json()["threads"]
    assert any(t["anchor"] and t["anchor"]["exact"] == "shard it. Then measure" for t in threads)


def test_a_reply_reaches_the_inbox_and_opens_at_its_thread_marked_new(
    browser: Browser,
    live_app: str,
    context: BrowserContext,
) -> None:
    artifact = publish(context)
    raj = browser.new_context(base_url=live_app)
    assert raj.request.post("/auth/dev", data={"login": "raj", "name": "Raj Patel"}, headers=WRITES).ok
    asked = raj.request.post(
        f"/api/artifacts/{artifact}/threads",
        data={"anchor": {"exact": "Then measure again."}, "body": "Measure what, exactly?"},
        headers=WRITES,
    ).json()
    raj.close()

    page = context.new_page()
    page.goto("/inbox")
    entry = page.locator(".entry", has_text="Measure what, exactly?")
    expect(entry).to_contain_text("Raj Patel")
    expect(entry).to_contain_text("Then measure again.")
    expect(page.get_by_role("link", name=re.compile(r"^Inbox, \d+ new$"))).to_be_visible()
    entry.locator("a").click()

    expect(page).to_have_url(re.compile(rf"/a/{artifact}\?t={asked['thread_id']}$"))
    note = page.locator(f'.thread.is-active[data-id="{asked["thread_id"]}"]')
    expect(note).to_contain_text("New")
    expect(note).to_contain_text("Measure what, exactly?")
    expect(page.get_by_role("button", name="1 new")).to_be_visible()
    deadline = time.monotonic() + DEADLINE
    while any(e["artifact"]["id"] == artifact for e in context.request.get("/api/inbox").json()["entries"]):
        assert time.monotonic() < deadline, "opening the artifact did not mark it read"
        time.sleep(0.1)


def test_a_token_is_shown_once_and_revoked(context: BrowserContext) -> None:
    page = context.new_page()
    page.goto("/tokens")

    page.fill("input >> nth=0", "nightly reporter")
    page.click("button:text-is('Mint')")
    expect(page.locator(".minted")).to_contain_text("lvt_")
    expect(page.locator(".minted")).to_contain_text("claude mcp add --transport http louvre")
    row = page.locator(".entry-row", has_text="nightly reporter")
    row.locator("button:text-is('Revoke')").click()
    expect(row).to_contain_text("revoked")


def test_a_reader_of_the_demo_is_asked_to_sign_in_to_reply(browser: Browser, live_app: str) -> None:
    context = browser.new_context(viewport={"width": 1440, "height": 900}, base_url=live_app)
    page = context.new_page()
    try:
        page.goto("/")
        expect(page.locator("h1")).to_have_text("Sign in to read")
        page.click("a:text-is('demo')")
        expect(page).to_have_url(re.compile(r"/demo$"))
        page.click("text=Checkout latency")
        shown(page)
        page.keyboard.press("j")

        expect(page.locator(".thread.is-active")).to_contain_text("Sign in to reply")
        expect(page.locator("button.add")).to_have_count(0)
    finally:
        context.close()


def changes_shown(page: Page) -> None:
    """Open the demo's report, compare its versions, and wait until the bridge has marked what changed."""
    page.goto("/demo")
    page.click("text=Checkout latency")
    shown(page)
    page.get_by_role("button", name="Changes", exact=True).click()
    page.wait_for_url(re.compile(r"changes=1$"))
    expect(page.get_by_role("button", name="Changes", exact=True)).to_have_attribute("aria-pressed", "true")
    frame = next(f for f in page.frames if "/content/" in f.url)
    frame.wait_for_function("() => CSS.highlights.get('louvre-change')?.size === 2")


def test_a_reader_compares_versions_steps_through_the_changes_and_opens_a_thread(context: BrowserContext) -> None:
    page = context.new_page()
    changes_shown(page)

    expect(page.locator(".changes-summary")).to_contain_text("3 changes: 15 words added, 5 removed")
    notes = page.locator(".rail > .thread.change")
    expect(notes.locator(".change-kind")).to_have_text(["Added", "Removed", "Rewritten"])
    expect(notes.nth(2)).to_contain_text("60 s")
    expect(notes.nth(2)).to_contain_text("five minutes")
    # Each note is level with its passage, so the notes run down the margin in the page's order.
    tops = [notes.nth(i).bounding_box()["y"] for i in range(3)]  # type: ignore[index]
    assert tops == sorted(tops)
    expect(page.locator(".changes-summary .fate-outcome").first).to_contain_text("Passage reworded or removed")
    expect(page.locator("button.add")).to_have_count(0)

    page.evaluate("document.activeElement.blur()")
    page.keyboard.press("j")
    expect(page.locator(".changes-summary.is-active")).to_be_visible()
    page.keyboard.press("j")
    expect(page.locator(".thread.change.is-active")).to_have_attribute("data-kind", "added")
    frame = next(f for f in page.frames if "/content/" in f.url)
    frame.wait_for_function("() => CSS.highlights.get('louvre-change-strong')?.size === 1")

    page.locator(".fate", has_text="Which dashboard").click()
    page.wait_for_url(re.compile(r"/a/a_[0-9a-f]+$"))
    expect(page.locator(".thread.is-active")).to_contain_text("Which dashboard is this from?")
    expect(page.locator(".thread.change")).to_have_count(0)
    expect(page.get_by_role("button", name="Changes", exact=True)).to_have_attribute("aria-pressed", "false")


def test_on_a_phone_the_comparison_opens_in_the_sheet_and_leaves_for_a_thread(browser: Browser, live_app: str) -> None:
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        color_scheme="dark",
        is_mobile=True,
        has_touch=True,
        base_url=live_app,
    )
    try:
        page = context.new_page()
        changes_shown(page)

        expect(page.locator(".changes-summary.is-active")).to_be_in_viewport()
        expect(page.locator(".thread.change").first).to_be_hidden()
        page.locator(".fate", has_text="Has the risk team").tap()

        page.wait_for_url(re.compile(r"/a/a_[0-9a-f]+$"))
        expect(page.locator(".thread.is-active")).to_contain_text("Has the risk team signed off on this?")
        expect(page.locator(".thread.is-active")).to_be_in_viewport()
    finally:
        context.close()


def board(page: Page) -> None:
    """Open the demo's board, and wait until it is fitted to the screen and the pages it draws have loaded."""
    page.goto("/b/design-study")
    page.wait_for_selector(".world[data-ready]:not([data-zooming])", state="attached")
    expect(page.locator(".board-frame")).to_have_count(6)
    for frame in page.frames[1:]:
        frame.wait_for_load_state()


def view(page: Page) -> tuple[float, float, float]:
    """Read how the board's canvas is drawn: its offset on the screen, and its scale.

    Returns:
        Its x, y, and scale.
    """
    drawn = page.evaluate(
        "() => { const m = new DOMMatrix(getComputedStyle(document.querySelector('.world')).transform);"
        " return [m.e, m.f, m.a]; }",
    )
    return float(drawn[0]), float(drawn[1]), float(drawn[2])


def drawn(page: Page, x: float | None = None, y: float | None = None, scale: float | None = None) -> None:
    """Wait until the board's canvas is drawn at the offset and scale given, any for one not given."""
    want = (x, y, scale)
    deadline = time.monotonic() + DEADLINE
    while True:
        got = view(page)
        if all(w is None or abs(g - w) <= CLOSE for g, w in zip(got, want, strict=True)):
            return
        assert time.monotonic() < deadline, f"the board is drawn at {got}, not {want}"
        page.wait_for_timeout(50)


def test_a_reader_pans_and_zooms_a_board_then_opens_a_frame_and_comments_on_it(context: BrowserContext) -> None:
    page = context.new_page()
    board(page)
    x, y, fitted = view(page)

    page.mouse.move(700, 600)
    page.mouse.down()
    page.mouse.move(600, 550, steps=5)
    page.mouse.up()
    drawn(page, x - 100, y - 50, fitted)
    assert "/b/design-study" in page.url, "a drag that ends on a frame opened it"

    page.mouse.wheel(0, -200)
    page.wait_for_function(f"new DOMMatrix(getComputedStyle(document.querySelector('.world')).transform).a > {fitted}")
    page.get_by_role("button", name="Fit to screen").click()
    drawn(page, x, y, fitted)
    page.get_by_role("button", name="Zoom in").click()
    drawn(page, scale=fitted * 1.25)
    page.keyboard.press("0")
    drawn(page, x, y, fitted)

    page.get_by_role("link", name="Open Direction: Gallery, Phone, 390").click()
    page.wait_for_url(re.compile(r"/a/a_\w+\?board=design-study&frame=gallery-phone$"))
    shown(page)
    assert page.locator(".sheet").bounding_box()["width"] <= 392  # type: ignore[index]
    select(page, "What we", "measured")
    page.click("button.add")
    page.fill(".thread[data-id=draft] textarea", "The phone's heads read well.")
    page.keyboard.press("Control+Enter")
    expect(page.locator(".thread.is-active .comments")).to_contain_text("The phone's heads read well.")

    page.get_by_role("link", name="Back to Design study, 2026-10-23").click()
    page.wait_for_url(re.compile(r"/b/design-study$"))


def test_on_a_phone_a_reader_drags_and_pinches_a_board_then_taps_a_frame_open(browser: Browser, live_app: str) -> None:
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        color_scheme="dark",
        is_mobile=True,
        has_touch=True,
        base_url=live_app,
    )
    try:
        page = context.new_page()
        board(page)
        touch = context.new_cdp_session(page)
        x, y, fitted = view(page)

        fingers(touch, [[(200, 500)], [(180, 480)], [(150, 460)]])
        drawn(page, x - 50, y - 40, fitted)

        fingers(touch, [[(150, 450), (250, 450)], [(125, 450), (275, 450)], [(100, 450), (300, 450)]])
        drawn(page, scale=fitted * 2)
        assert "/b/design-study" in page.url

        page.get_by_role("button", name="Fit to screen").tap()
        page.get_by_role("link", name="Open Direction: Studio, Laptop, 1440").tap()
        page.wait_for_url(re.compile(r"frame=studio-laptop$"))
        expect(page.locator("iframe.exhibit")).to_be_visible()
    finally:
        context.close()


def test_on_a_phone_a_board_zoomed_out_paints_little_past_its_frames(browser: Browser, live_app: str) -> None:
    """A frame's shadow reaches past it by the sheet's few pixels on the canvas at any zoom, not more as it zooms out.

    A shadow of one size on the screen grew to eight times the pages' own area at the least zoom, and panning that
    took more memory than a phone's browser has.
    """
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        color_scheme="dark",
        is_mobile=True,
        has_touch=True,
        base_url=live_app,
    )
    try:
        page = context.new_page()
        board(page)
        zoom_out = page.get_by_role("button", name="Zoom out")
        while view(page)[2] > MIN_SCALE + CLOSE:
            zoom_out.tap()
        reach = page.evaluate(
            "() => getComputedStyle(document.querySelector('.board-frame')).boxShadow"
            ".split(/,(?![^(]*\\))/).map((s) => s.match(/-?[\\d.]+px/g).map(parseFloat))"
            ".map(([x, y, blur, spread]) => Math.max(Math.abs(x), Math.abs(y)) + blur + spread)",
        )
        assert max(reach) <= SHADOW_REACH, f"a frame's shadows reach {reach} canvas pixels past it"
    finally:
        context.close()


def test_on_a_tablet_a_pinch_puts_the_pages_away_until_it_stops_without_reloading_them(
    browser: Browser,
    live_app: str,
) -> None:
    """While a pinch zooms, a frame is its sheet alone; once it stops, each page is drawn again as it was, not reloaded.

    Each step of a zoom redrew all six pages at the new size, and a phone's browser ran out of memory doing it. A
    tablet draws all six, where a phone draws two at most.
    """
    context = browser.new_context(
        viewport={"width": 820, "height": 1180},
        color_scheme="dark",
        is_mobile=True,
        has_touch=True,
        base_url=live_app,
    )
    try:
        page = context.new_page()
        board(page)
        expect(page.locator(".board-frame iframe")).to_have_count(6)
        page.evaluate(
            "() => { window.loads = 0; window.hid = false;"
            " for (const f of document.querySelectorAll('.board-frame iframe'))"
            " f.addEventListener('load', () => { window.loads += 1 });"
            " new MutationObserver(() => { const f = document.querySelector('.board-frame iframe');"
            " window.hid ||= getComputedStyle(f).display === 'none' })"
            ".observe(document.querySelector('.world'), { attributes: true }) }",
        )
        touch = context.new_cdp_session(page)
        fingers(touch, [[(150 - n * 10, 450), (250 + n * 10, 450)] for n in range(6)])
        deadline = time.monotonic() + DEADLINE
        while not page.evaluate("window.hid"):
            assert time.monotonic() < deadline, "the pages were drawn all through the pinch"
            page.wait_for_timeout(50)
        expect(page.locator(".world[data-zooming]")).to_have_count(0)
        expect(page.locator(".board-frame iframe").first).to_be_visible()
        assert page.evaluate("window.loads") == 0, "a page was loaded again"
    finally:
        context.close()


def test_on_a_phone_a_board_draws_a_page_only_zoomed_in_to_it_and_two_at_most(browser: Browser, live_app: str) -> None:
    """Fitted to a phone, a board draws its frames' sheets alone; zoomed in, the pages it shows most of, two at most.

    Six pages at once are more than a phone's browser has the memory for: it crashed as the board loaded.
    """
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        color_scheme="dark",
        is_mobile=True,
        has_touch=True,
        base_url=live_app,
    )
    try:
        page = context.new_page()
        board(page)
        expect(page.locator(".board-frame iframe")).to_have_count(0)

        for _ in range(3):
            page.get_by_role("button", name="Zoom in").tap()
        expect(page.locator(".board-frame[data-live] iframe").first).to_be_visible()
        assert 1 <= page.locator(".board-frame iframe").count() <= LIVE_COUNT

        page.get_by_role("button", name="Fit to screen").tap()
        expect(page.locator(".board-frame iframe")).to_have_count(0)
    finally:
        context.close()


def test_on_a_phone_a_pinch_off_the_canvas_does_not_zoom_the_page(browser: Browser, live_app: str) -> None:
    """A pinch on the header or the toolbar leaves the page at its size: the browser's zoom draws every frame larger."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        color_scheme="dark",
        is_mobile=True,
        has_touch=True,
        base_url=live_app,
    )
    try:
        page = context.new_page()
        board(page)
        touch = context.new_cdp_session(page)
        for bar in ("header", ".toolbar"):
            box = page.locator(bar).first.bounding_box()
            assert box is not None
            y = int(box["y"] + box["height"] / 2)
            fingers(touch, [[(170, y), (220, y)], *([(170 - n * 20, y), (220 + n * 20, y)] for n in range(1, 8))])
            assert page.evaluate("visualViewport.scale") == 1, f"a pinch on the {bar} zoomed the page"
    finally:
        context.close()


def test_the_design_study_is_a_board_to_read_without_a_database_or_signing_in(browser: Browser, live_app: str) -> None:
    context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark", base_url=live_app)
    try:
        page = context.new_page()
        page.goto("/directions")
        page.click("text=The directions, as a board")
        page.wait_for_selector(".world[data-ready]", state="attached")
        expect(page.locator(".board-frame iframe")).to_have_count(6)

        page.get_by_role("link", name="Open Direction: Margins, Phone, 390").click()
        page.wait_for_url(re.compile(r"/directions/2026-10-23-directions/margins$"))
    finally:
        context.close()


def fingers(session: CDPSession, steps: Sequence[Sequence[tuple[int, int]]]) -> None:
    """Touch the screen: the fingers go down where the first step has them, move through the rest, and lift."""
    for i, step in enumerate(steps):
        points = [{"x": px, "y": py, "id": n} for n, (px, py) in enumerate(step)]
        session.send(
            "Input.dispatchTouchEvent",
            {"type": "touchStart" if i == 0 else "touchMove", "touchPoints": points},
        )
    session.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


def call(context: BrowserContext, secret: str, name: str, **arguments: object) -> str:
    """Call a tool through the MCP server with a token's secret, and return its text."""
    called = context.request.post(
        "/mcp",
        data={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
        headers={"Authorization": f"Bearer {secret}"},
    ).json()
    assert called["result"]["isError"] is False, called
    return str(called["result"]["content"][0]["text"])


def test_a_person_answers_an_agents_decision_and_the_agent_reads_it_back(context: BrowserContext) -> None:
    secret = context.request.post(
        "/api/tokens",
        data={"name": "canopy worker", "namespace": "canopy/ana", "scopes": ["read", "publish", "comment"]},
        headers=WRITES,
    ).json()["secret"]
    artifact = json.loads(
        call(context, secret, "artifact_publish", title="Cache", content_type="text/html", content=PAGE),
    )
    asked = json.loads(
        call(
            context,
            secret,
            "decision_create",
            artifact_id=artifact["artifact_id"],
            question="Shard the cache now?",
            options=[
                {"label": "Shard it", "anchor": {"exact": "We should shard it."}},
                {"label": "Measure first", "detail": "A week of data.", "anchor": {"exact": "Then measure again."}},
            ],
            asked=["ana"],
        ),
    )
    waiting = context.request.get("/api/decisions").json()["awaiting"]
    page = context.new_page()
    page.goto(f"/a/{artifact['artifact_id']}?decision={asked['decision_id']}")
    expect(page.frame_locator("iframe.exhibit").locator("h1")).to_have_text("Cache report")
    card = page.locator(f"#decision-{asked['decision_id']}")
    frame = next(f for f in page.frames if "/content/" in f.url)

    expect(card).to_contain_text("Your answer is wanted")
    expect(card).to_contain_text("(Agent, for Ana Ruiz)")
    expect(page.locator(".masthead .awaiting")).to_have_text(str(waiting))
    card.locator(".option", has_text="Measure first").hover()
    frame.wait_for_function("CSS.highlights.get('louvre-strong')?.size === 1")
    card.get_by_role("radio", name="Shard it").check()
    card.locator("textarea").fill("Before the sale.")
    card.locator("button:text-is('Answer')").click()

    expect(card).to_contain_text("your choice")
    expect(card.locator(".answers")).to_contain_text("Ana Ruiz chose Shard it")
    expect(card.locator(".answer-note")).to_have_text("Before the sale.")
    expect(page.locator(".masthead .awaiting")).to_have_count(1 if waiting > 1 else 0)
    events = [json.loads(line) for line in call(context, secret, "decision_feed").splitlines()]
    mine = [e for e in events if e.get("decision_id") == asked["decision_id"]]
    assert [(e["kind"], e["choices"], e["note"], e["author"]["kind"]) for e in mine] == [
        ("decision_asked", [], "", "agent"),
        ("decision_answered", ["o1"], "Before the sale.", "person"),
    ]

    page.goto("/decisions")
    expect(page.locator(".entry", has_text="Shard the cache now?")).to_contain_text("Answered")
