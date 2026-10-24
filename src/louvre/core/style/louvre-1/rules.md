# Louvre's house style, louvre-1

A guide to writing an HTML artifact that reads like Louvre's own pages: a stylesheet to inline, the components it
styles, and how to write a page people read and comment on. It is optional. A Markdown artifact is shown in it already.

## When to use it

- **Use it** for a page people read: a report, a decision, a plan, a review, notes. It gives the page Louvre's type
  and color, dark and light, with nothing to design.
- **Write Markdown instead** when the page is prose, lists, and a table or two: Louvre renders it in this style, and
  a Markdown page is quicker to write and to revise.
- **Use your own look** for a mock-up of a product's screen: it should look like that product, not like Louvre. The
  rules under "Self-contained", "Phones", and "Scripts" still hold.

## Kinds

Each kind of artifact has a starter page: `style_get` with `kind` returns it, and each is a resource,
`louvre://style/louvre-1/starters/<kind>.html`. Start from the one closest to your page.

| Kind | For | Its components |
|---|---|---|
| `report` | Findings, with the numbers behind them | KPIs with their change, a chart with a legend, callouts, a table of numbers |
| `decision` | A choice between options, and the one recommended | Requirements as facts, options side by side, a comparison table, a risk, a redline, next steps |
| `plan` | What will be done, in steps, with its risks | Facts, numbered steps with their status, a risk, open questions |

## The page

- Inline the stylesheet in a `<style>` element in `<head>`, and put `class="louvre"` on `<body>`. The starter pages
  do both: replace their words, keep what the page needs, and drop the rest.
- Give the page `<meta charset="utf-8">`, `<meta name="viewport" content="width=device-width, initial-scale=1">`, and
  a `<title>` that says what the page is. The artifact's title in `artifact_publish` says the same.
- Put the content in one `<main>`, or one `<div class="l-page">`. Open it, in this order, with:
  - `<p class="l-kicker">`: the kind of page and who it is for, such as "Report · Payments".
  - `<h1>`: the finding or the question, not the topic. "Checkout is back under 450 ms", not "Checkout latency".
  - `<p class="l-lede">`: the finding in a sentence or two, for a reader who reads nothing else.
  - `<p class="l-meta">`: where it comes from: the data and its dates, the ticket, who or what wrote it, and when.
- Sections are `<h2>`, named for what they say. Use `<h3>` inside a section, never deeper.
- End with `<footer>`: the sources, and how the page was made, so a reader can check a number.

## Writing for comments

People comment by selecting words. A comment quotes its passage, and a later version keeps the comment where the same
words still stand.

- Lead with the finding, then the evidence. A reader who stops after the lede has what matters.
- One claim to a sentence, so a comment can quote exactly the claim it disputes.
- Short paragraphs, plain words, and the active voice. Spell out an abbreviation the first time.
- Every number has its unit, kept on its line with `&nbsp;` (`430&nbsp;ms`), and something to compare it with: last
  week, the target, the other option.
- Dates are absolute (2026-10-24, or 24 October), never "yesterday": a page is read long after it is published.
- Say what you do not know, and how sure you are.
- Put every word a reader should see in the page, as text: not only in an image, a tooltip, or a closed `<details>`.
  What is hidden cannot be read at a glance or quoted in a comment.
- Never put in a secret, a token, a password, or a person's private data. No tool deletes an artifact.

## Components

Each is in at least one starter page. The class goes on the element shown.

- **KPIs**: `<div class="l-kpis">` of `<div class="l-kpi"><span>label</span><b>value</b><em>change</em></div>`.
  Three or four, each a number a reader would ask for first. The `<em>` is optional; give it `l-good` or `l-bad`
  when the change is good or bad news.
- **Figure**: `<figure>` with a `<figcaption>` that says what it shows and in what unit, around a chart, an image, or
  a table. `<div class="l-figure">` looks the same, for a box with no caption.
- **Callout**: `<div class="l-callout">` for the one thing a reader must not miss; `l-callout l-risk` for a risk or a
  regression. One or two to a page: more, and none stands out.
- **Tag**: `<span class="l-tag">Draft</span>`, a status in a word or two. Add `l-good`, `l-bad`, or `l-muted` to color
  it.
- **Options**: `<div class="l-compare">` of `<div class="l-option">`, each opening with an `<h3>`. The recommended one
  is `l-option l-chosen`, with `<span class="l-tag">Recommended</span>` in its heading. Two or three, side by side;
  they stack on a phone.
- **Steps**: `<ol class="l-steps">`, each `<li>` a step, opening with what it delivers in `<b>`, numbered in the
  margin. A step's status is a tag at its end.
- **Facts**: `<dl>` of `<dt>` and `<dd>`: label and value, such as an owner, a date, a goal. Two columns, one on a
  phone.
- **Redline**: `<del>` for words taken out and `<ins>` for words put in, as in a policy change or a diff of text.
- **Numbers in a table**: `class="l-num"` on each `<th>` and `<td>` of a numeric column, so they line up on the right.
  Give a cell `l-good` or `l-bad` to color a change.
- **A wide table**: wrap it in `<div class="l-scroll">`, so it scrolls inside its wrapper and the page does not.
- **Code**: `<pre><code>` for a block, `<code>` inline.
- **Quote**: `<blockquote>` for words quoted from elsewhere.
- **Muted**: `class="l-muted"` for text that is beside the point, such as a footnote's marker.

## Color

Every color is a custom property, defined for both themes. Use them in your own styles and SVG, never a fixed color,
and the page works dark and light.

| Property | For |
|---|---|
| `--l-bg`, `--l-card` | The page, and a box on it |
| `--l-ink`, `--l-muted` | Text, and text that is secondary |
| `--l-rule` | Hairlines, axes, and gridlines |
| `--l-accent` | Links, the recommended option, and the series a chart is about |
| `--l-good`, `--l-bad` | A change that is good news, and one that is bad |
| `--l-c1` to `--l-c4` | A chart's series, in order: `--l-c1` is the accent |

- The accent marks what matters most: most of the page is ink on the background.
- Never say a thing by color alone. A good change also has its sign and its words ("&minus;62%, faster"), and a
  chart's series also has its label.
- Every color here reads at 4.5:1 or better on `--l-bg` and `--l-card`, in both themes, so each can color text too.

## Charts

Draw a chart as inline SVG, in a figure, with the chart's class:

```html
<figure>
<figcaption>p95 checkout by day, in milliseconds</figcaption>
<svg class="l-chart" viewBox="0 0 440 200" role="img" aria-label="p95 fell from 1,180 ms on Monday to 430 ms">
<line x1="50" y1="170" x2="430" y2="170" stroke="var(--l-rule)"/>
<text x="44" y="174" text-anchor="end">0</text>
<polyline fill="none" stroke="var(--l-c1)" stroke-width="3" points="60,13 180,74 300,108 420,113"/>
</svg>
<ul class="l-legend"><li class="l-c1">This week</li><li class="l-c2">Last week</li></ul>
</figure>
```

- `class="l-chart"` sets the SVG's text in Louvre's sans, in the muted ink, and makes it the figure's width.
- Make the `viewBox` about 440 wide. The chart scales to the page, and its text with it: the chart's 14 units read at
  about 10 px on a phone and 18 px on a laptop. Never set text smaller than 13 units.
- Color each series with `stroke` or `fill` set to `var(--l-c1)` to `var(--l-c4)`, in order; draw a baseline or
  everything else in `var(--l-muted)`. Four series at most: more, and a reader cannot tell them apart. Draw small
  multiples instead.
- Name each series in a `<ul class="l-legend">` under the chart, each `<li>` with its series' class, `l-c1`, `l-c2`,
  `l-c3`, or `l-c4`, or label the line itself at its end.
- Axes and gridlines are `var(--l-rule)`, one pixel. Label a few round values, not every tick, and leave the labels
  room inside the `viewBox`: what falls outside it is cut off.
- A bar starts at zero. A line may not, if its axis is labeled.
- `role="img"` and an `aria-label` that says what the chart shows, in words: the finding, not "a chart".
- Say the chart's finding in the text too: a reader who cannot see the chart still has it.
- A chart of a few numbers is better as a table, or as KPIs.

## Tables

- A table for numbers a reader compares; a list, or facts, for anything else.
- Four columns at most on a page a phone reads; wrap a wider one in `l-scroll`.
- The first column names the row. Units go in the header, "p95 (ms)", or in each cell with `&nbsp;`.
- Order rows by what the reader looks for: largest first, or the order of time.

## Phones

People read on phones as well as laptops, at widths from 320 px.

- Nothing may be wider than the page: an image or an SVG scales down by itself, and a wide table goes in `l-scroll`.
- Never set a width in pixels on a box. Use the components, which wrap and stack.
- A line of text in a `<pre>` scrolls inside its box; keep code lines short.

## Self-contained

A page in Louvre loads nothing from the network: its policy refuses every request to another address. No external
stylesheet, font, script, or image.

- The style's own faces are the one exception: its stylesheet loads them from Louvre, so a page in the style is set as
  Louvre's own pages are. Shown anywhere else, it falls back to the reader's own serif and sans.
- An image goes inline: SVG markup, or a `data:` URL. Keep each image small; prefer SVG.
- Any other font goes inline as a `data:` URL, or not at all.
- A link to another page is fine: it opens in a new tab. A link to `#id` moves within the page.

## Scripts

A page may run scripts, inline, in a sandbox: they cannot reach the reader's session, storage, or the network.

- The page reads whole without them. A script may sort a table or switch a chart's series, but never adds the words a
  reader needs.
- No `localStorage`, `sessionStorage`, or cookies: the sandbox refuses them, and a script that uses them throws.
- Nothing that moves by itself: no autoplay, no carousel.

## Revising

- A revision is a new version of the same artifact: publish with its `artifact_id`. Its threads carry over by their
  passages' words.
- Keep a passage's words when the passage still holds, so its thread stays on it. Change them when the comment asked
  you to; a thread whose words are gone reads as gone from that version, for its author to resolve.
- Answer a thread you addressed, saying what changed, then resolve it.

## Before publishing

Call `style_check` with the page. It reads the markup and finds what a parser can see of this guide: errors for what
would not work in Louvre (a request to the network, storage, a starter page's words left in), and warnings for the
rest. Fix every error; fix a warning unless the page has a reason for it. Then read the page once more yourself, for
what no parser can see:

- The `<h1>` and the lede say the finding, and the title says the same.
- Every number has its unit and its comparison; every date is absolute.
- No color says anything alone; every chart has a label in words.
- Nothing is wider than a phone; nothing loads from the network.
- No secret, token, or private data is on the page.
