"""What people do on Louvre's pages, in Chromium: comment on words they select, reply, resolve, and mint tokens.

These drive a browser, so they run with the screen matrix (`make screens`, CI's screens job), against the live app on
the test database. A selection is made inside the artifact's sandboxed frame, as a reader's would be, so the bridge's
reading of the page and the server's must agree for a comment to land.
"""

import json
import os
import re
from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, expect

from tests.conftest import WRITES

#: Run with the screen matrix: `1` or `update`.
MODE = os.environ.get("LOUVRE_SCREENS", "")
#: A page an agent publishes: a passage that crosses an inline tag, and one that crosses a block.
PAGE = (
    "<!doctype html><html><head><title>Cache report</title></head><body><main>"
    "<h1>Cache report</h1><p>The cache is <em>slow under load</em>, because every miss takes the lock.</p>"
    "<p>We should shard it.</p><p>Then measure again.</p></main></body></html>"
)

pytestmark = pytest.mark.skipif(MODE not in {"1", "update"}, reason="drives a browser: run `make screens`")


@pytest.fixture
def context(browser: Browser, live_app: str) -> Iterator[BrowserContext]:
    """A browser signed in as Ana, at a laptop's size."""
    made = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark", base_url=live_app)
    signed = made.request.post("/auth/dev", data={"login": "ana", "name": "Ana Ruiz"}, headers=WRITES)
    assert signed.status == 204
    yield made
    made.close()


def publish(context: BrowserContext) -> str:
    """Publish PAGE as Ana's agent, through the MCP server with a token she mints, and return its id."""
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
                "arguments": {"title": "Cache report", "content_type": "text/html", "content": PAGE},
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
    frame = page.frames[1]
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
        page.click("text=Checkout latency")
        shown(page)
        page.keyboard.press("j")

        expect(page.locator(".thread.is-active")).to_contain_text("Sign in to reply")
        expect(page.locator("button.add")).to_have_count(0)
    finally:
        context.close()
