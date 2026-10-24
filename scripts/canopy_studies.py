"""Copy canopy's two UI studies into the demo, as pages it publishes (louvre.core.demo).

It reads them from a checkout of canopy, CANOPY, its `docs/ui-explorations/`. The style study's pages are copied as
they are. The structure study is one page, `redrawn.html`, whose script draws each direction's screens into a board of
its own; this draws each in Chromium and writes it as a page of its own, static, with only the styles it uses, so the
demo hangs them on one of Louvre's boards and each takes its own threads. Its "Where we are" screens are canopy's
screenshot baselines at the commit the study names, read from CANOPY's history, which must hold that commit
(`git fetch --depth=1 origin <sha>`), and each is written beside the page that shows it.

    uv run python scripts/canopy_studies.py CANOPY
"""

import json
import shutil
import subprocess
from pathlib import Path

import click
from playwright.sync_api import sync_playwright

#: Where the demo's copies go.
OUT = Path(__file__).resolve().parents[1] / "src" / "louvre" / "core" / "demo" / "canopy"
#: The studies, by their directory in canopy's `docs/ui-explorations/`.
STYLE = "2026-10-08-style"
STRUCTURE = "2026-10-19-structure"
#: The commit whose screenshot baselines the structure study shows, and where they are in it.
SCREENSHOTS_AT = "8db8772f821b2f3684aaca82dc0bd5e077abf9b4"
SCREENSHOTS = "ui/e2e/screenshots.spec.ts-snapshots"
#: Draws every page of the structure study, in its own page, from its own functions: each a name, a title, whether it
#: is a drawing of canopy (`mock`, at 1440 by 900) or the study's own words (`study`), its markup, and the screenshot
#: it shows, if any.
DRAW = """() => {
  const pages = [];
  const page = (name, title, kind, html, shot) => pages.push({ name, title, kind, html, shot });
  const shown = html => { const box = document.createElement('div'); box.innerHTML = html; return box; };
  // The board's controls, which a page of one screen has no use for, and the marks, which save only on claude.ai.
  const study = (box, ...drop) => {
    box.querySelectorAll(['.tabs', '.stage-wrap', '.stage-cap', ...drop].join(',')).forEach(n => n.remove());
    box.querySelectorAll('.verdict > :not(h2)').forEach(n => n.remove());
    return box.innerHTML;
  };
  const mock = (cls, html) => `<div class="mock ${cls}" data-mode="dark">${html}</div>`;
  const where = 'Where we are';
  page('today', where, 'study', study(shown(today()), '.shot-grid'));
  for (const [key, shot] of Object.entries(SHOTS)) {
    state.shot = key;
    const box = shown(today());
    const name = `today-${key}`;
    box.querySelector('h1').textContent = `Today\u2019s ${shot.label} page`;
    box.querySelector('.lede').remove();
    box.querySelector('.shot img').setAttribute('src', `${name}.png`);
    const kept = [box.querySelector('header'), box.querySelector('.shot-grid')];
    page(name, `${where}: ${shot.label}`, 'study', kept.map(n => n.outerHTML).join(''), key);
  }
  for (const [id, d] of Object.entries(DIRS)) {
    const named = `Direction ${d.n}: ${d.name}`;
    state.screen = 'map';
    page(id, named, 'study', study(shown(dirBoard(id))));
    for (const [screen, label] of [['inbox', 'Inbox'], ['ticket', 'Ticket ABC-102'], ['run', 'Run 39']]) {
      const cls = `m${d.n}${id === 'd2' && screen === 'ticket' ? ' info4' : ''}`;
      page(`${id}-${screen}`, `${named}, ${label}`, 'mock', mock(cls, d.render[screen]()));
    }
  }
  // Without the marks so far, the overall mark, and the next step once marked.
  const compared = shown(compare());
  compared.querySelector('.pick-list').closest('.panel').remove();
  compared.lastElementChild.remove();
  page('compare', 'Compare and pick', 'study', study(compared, '.verdict'));
  const four = 'Mailroom, round four';
  state.look = 'drawn';
  page('r4', four, 'study', study(shown(r4Board())));
  for (const [screen, label, draw] of R4_SCREENS) {
    const info = screen === 'ticket' ? ' info4' : '';
    // Its first three screens, as drawn, are Mailroom's in round three, which the demo shows again.
    if (!['inbox', 'ticket', 'run'].includes(screen)) {
      page(`r4-${screen}`, `${four}: ${label}`, 'mock', mock(`m2${info}`, draw()));
    }
    page(`r4-today-${screen}`, `${four} in today\u2019s tokens: ${label}`, 'mock', mock(`m2 today${info}`, draw()));
  }
  return pages.map(p => Object.fromEntries(Object.entries(p).filter(([, v]) => v !== undefined)));
}"""
#: Keeps only the style rules a page's markup uses, in either theme: a rule stays when a selector of it, without its
#: pseudo-classes and theme, matches something on the page, or when it styles the document as a whole.
PRUNE = """() => {
  const whole = /^(?::root|html|body|\\*)/;
  const bare = s => s
    .replace(/\\[data-(?:mode|theme)="[a-z]+"\\]/g, '')
    .replace(/::?[a-z-]+(?:\\([^)]*\\))?/g, '')
    .trim();
  const matches = s => { try { return !!document.querySelector(bare(s) || '*'); } catch (_) { return true; } };
  const used = s => whole.test(s.trim()) || matches(s);
  const kept = rules => [...rules].flatMap(r => {
    if (r instanceof CSSStyleRule) return r.selectorText.split(',').some(used) ? [r.cssText] : [];
    if (r instanceof CSSMediaRule) {
      const inner = kept(r.cssRules);
      return inner.length ? [`@media ${r.conditionText} {\\n${inner.join('\\n')}\\n}`] : [];
    }
    return [r.cssText];
  });
  return kept(document.styleSheets[0].cssRules).join('\\n');
}"""
#: Gives a drawing of canopy the reader's theme, as the study's own words take it from their styles.
THEMED = (
    "<script>if (matchMedia('(prefers-color-scheme: light)').matches) "
    "document.querySelector('.mock').dataset.mode = 'light';</script>"
)


@click.command()
@click.argument("canopy", type=click.Path(exists=True, file_okay=False, path_type=Path))
def main(canopy: Path) -> None:
    """Copy the style study and draw the structure study's pages from canopy's checkout in CANOPY."""
    studies = canopy / "docs" / "ui-explorations"
    shutil.rmtree(OUT / STYLE, ignore_errors=True)
    shutil.copytree(studies / STYLE, OUT / STYLE, ignore=shutil.ignore_patterns("*.md"))
    out = OUT / STRUCTURE
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    source = (studies / STRUCTURE / "redrawn.html").read_text(encoding="utf-8")
    css = source[source.index("<style>") + len("<style>") : source.index("</style>")]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        # Its fonts are Google's, which an artifact may not load: the pages fall back as the style study's do.
        page.route("**/*", lambda route: route.continue_() if route.request.url.startswith("file:") else route.abort())
        page.goto((studies / STRUCTURE / "redrawn.html").resolve().as_uri())
        drawn: list[dict[str, str]] = page.evaluate(DRAW)
        for one in drawn:
            body = _body(one)
            page.set_content(f"<style>{css}</style>{body}")
            styles = page.evaluate(PRUNE)
            (out / f"{one['name']}.html").write_text(_page(one, styles, body), encoding="utf-8")
            if "shot" in one:
                (out / f"{one['name']}.png").write_bytes(_screenshot(canopy, one["shot"]))
        browser.close()
    click.echo(json.dumps([one["name"] for one in drawn]))


def _body(one: dict[str, str]) -> str:
    if one["kind"] == "mock":
        return one["html"] + THEMED
    return f'<main><div class="board">{one["html"]}</div></main>'


def _page(one: dict[str, str], styles: str, body: str) -> str:
    margin = "body { margin: 0; }\n" if one["kind"] == "mock" else ""
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{one['title']}</title>\n<style>\n{margin}{styles}\n</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
    )


def _screenshot(canopy: Path, shot: str) -> bytes:
    """Read one of the baselines the study shows, at the commit it names.

    Returns:
        The PNG.
    """
    name = {"ticket": "tickets-ABC-102", "run": "runs-39", "review": "reviews-4"}.get(shot, shot)
    return subprocess.run(  # noqa: S603  (a fixed git command over canopy's checkout)
        ["git", "-C", str(canopy), "show", f"{SCREENSHOTS_AT}:{SCREENSHOTS}/{name}-dark-root-linux.png"],  # noqa: S607
        check=True,
        capture_output=True,
    ).stdout


if __name__ == "__main__":
    main()
