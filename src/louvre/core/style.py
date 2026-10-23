"""Louvre's house style for artifacts (REQUIREMENTS U6): a stylesheet an agent may use, and the rules for using it.

It is Annotated's type and color (ui/DESIGN.md) made for a page inside the artifact's frame: dark first, light when the
reader's system is, every color a custom property. A page cannot load fonts from the network in its sandbox, so it
names the faces and falls back to the reader's own serif and sans. Louvre wraps every Markdown artifact in it, and the
`style_get` tool hands it to an agent writing HTML, which inlines it in a `<style>` element. The version is in the
name: a later style is a new version, and never restyles a page already published.
"""

#: The style's name and version, as a page that uses it names it.
VERSION = "louvre-1"

#: The stylesheet. Every class it styles starts `l-`, and the page's root takes `class="louvre"`.
CSS = """/* louvre-1: Louvre's house style for artifacts. Put class="louvre" on <body>. */
:root {
    color-scheme: dark light;
    --l-bg: #1c1915;
    --l-card: #23201b;
    --l-ink: #ece5d8;
    --l-muted: #a69c8c;
    --l-rule: #322c24;
    --l-accent: #d9776c;
    --l-good: #6fbf8e;
    --l-serif: "Source Serif 4", "Iowan Old Style", Georgia, "Times New Roman", serif;
    --l-display: Fraunces, "Iowan Old Style", Georgia, serif;
    --l-sans: "Instrument Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
    --l-mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: light) {
    :root {
        --l-bg: #fffdf8;
        --l-card: #f6f1e7;
        --l-ink: #1f1b16;
        --l-muted: #6d6458;
        --l-rule: #e0d6c4;
        --l-accent: #8a2f2a;
        --l-good: #2f7a4d;
    }
}
* { box-sizing: border-box; }
body.louvre {
    margin: 0;
    background: var(--l-bg);
    color: var(--l-ink);
    font: 17px/1.6 var(--l-serif);
    -webkit-text-size-adjust: 100%;
}
.louvre main, .louvre .l-page {
    max-width: 42.5rem;
    margin: 0 auto;
    padding: 2.5rem 1.25rem 4rem;
}
@media (min-width: 600px) {
    body.louvre { font-size: 19px; line-height: 1.62; }
    .louvre main, .louvre .l-page { padding: 3rem 2rem 4.5rem; }
}
.louvre h1, .louvre h2, .louvre h3 {
    font-family: var(--l-display);
    font-weight: 600;
    line-height: 1.15;
    letter-spacing: -0.01em;
}
.louvre h1 { margin: 0 0 1rem; font-size: 1.75em; }
.louvre h2 { margin: 2.2em 0 0.4em; font-size: 1.25em; }
.louvre h3 { margin: 1.8em 0 0.3em; font-size: 1.05em; }
.louvre p, .louvre ul, .louvre ol { margin: 0 0 1em; }
.louvre a { color: var(--l-accent); text-underline-offset: 0.2em; }
.louvre .l-kicker {
    margin: 0 0 0.5rem;
    color: var(--l-muted);
    font: 600 0.72rem/1.4 var(--l-sans);
    letter-spacing: 0.1em;
    text-transform: uppercase;
}
.louvre .l-lede { font-size: 1.1em; }
.louvre .l-muted { color: var(--l-muted); }
.louvre blockquote {
    margin: 1.2em 0;
    padding: 0.2em 0 0.2em 1em;
    border-left: 2px solid var(--l-rule);
    color: var(--l-muted);
}
.louvre code {
    padding: 0.1em 0.3em;
    border-radius: 4px;
    background: var(--l-card);
    font: 0.88em var(--l-mono);
}
.louvre pre {
    overflow-x: auto;
    padding: 1em;
    border: 1px solid var(--l-rule);
    border-radius: 8px;
    background: var(--l-card);
}
.louvre pre code { padding: 0; background: none; }
.louvre table {
    width: 100%;
    margin: 1em 0;
    border-collapse: collapse;
    font: 0.8em/1.5 var(--l-sans);
    font-variant-numeric: tabular-nums;
}
.louvre th, .louvre td {
    padding: 0.5em 0.75em 0.5em 0;
    border-bottom: 1px solid var(--l-rule);
    text-align: left;
}
.louvre th { color: var(--l-muted); font-weight: 500; }
.louvre hr { margin: 2em 0; border: 0; border-top: 1px solid var(--l-rule); }
.louvre img, .louvre svg { max-width: 100%; height: auto; }
.louvre .l-figure, .louvre figure {
    margin: 1.2em 0;
    padding: 1em;
    border: 1px solid var(--l-rule);
    border-radius: 12px;
    background: var(--l-card);
}
.louvre figcaption { margin-bottom: 0.6em; font: 600 0.8em/1.4 var(--l-sans); }
.louvre .l-callout {
    margin: 1.2em 0;
    padding: 0.8em 1em;
    border-left: 3px solid var(--l-good);
    border-radius: 0 10px 10px 0;
    background: var(--l-card);
}
.louvre .l-kpis {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
    gap: 0.75rem;
    margin: 1.5em 0;
}
.louvre .l-kpi {
    padding: 0.9em 1em;
    border: 1px solid var(--l-rule);
    border-radius: 12px;
    background: var(--l-card);
    font-family: var(--l-sans);
}
.louvre .l-kpi b { display: block; font-size: 1.5em; font-variant-numeric: tabular-nums; }
.louvre .l-kpi span { color: var(--l-muted); font-size: 0.78em; }
"""

#: How to use it, for an agent: what `style_get` returns beside the stylesheet.
RULES = """Louvre's house style, louvre-1. Optional: use it when a page should look like Louvre's own.

- Inline the stylesheet in a <style> element in <head>, and put class="louvre" on <body>. A page in Louvre loads
  nothing from the network: no external stylesheets, fonts, scripts, or images. Images and fonts go inline as data:
  URLs; charts as inline SVG.
- Put the page's content in <main>. Open with <p class="l-kicker"> (what it is, such as "Report"), an <h1>, and a
  <p class="l-lede"> that says the finding in a sentence or two.
- Components: <div class="l-kpis"> of <div class="l-kpi"><span>label</span><b>value</b></div>; <figure> with a
  <figcaption> around a chart or table; <div class="l-callout"> for the one thing a reader must not miss; <table> for
  numbers, which line up by themselves.
- Dark first: the style follows the reader's color scheme. Use its custom properties (var(--l-ink), var(--l-muted),
  var(--l-accent), var(--l-rule), var(--l-card)) in your own SVG and styles, never fixed colors, so both themes work.
- Write for a phone too: nothing wider than the page; tables of a few columns; a number keeps its unit with &nbsp;.
- People comment on your words: keep each claim in a sentence of its own, so a comment can quote it.
"""
