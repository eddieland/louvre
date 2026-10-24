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
| `report` | Findings, with the numbers behind them | KPIs with their change, a line chart with notes, callouts, a table of numbers |
| `decision` | A choice between options, and the one recommended | Requirements as facts, options side by side, a comparison table, a bar chart, a risk, a redline, next steps |
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
| `--l-accent` | Links, the recommended option, and what a chart is about |
| `--l-good`, `--l-bad` | A change that is good news, and one that is bad |

- One accent marks what matters most, as on Louvre's own pages: most of the page is ink on the background. There is no
  palette of series colors: a chart's other series are muted ink.
- Never say a thing by color alone. A good change also has its sign and its words ("&minus;62%, faster"), and a
  chart's series also has its label.
- Every color here reads at 4.5:1 or better on `--l-bg` and `--l-card`, in both themes, so each can color text too.

## Charts

Call `style_chart` with the data, and put the figure it returns in the page: it draws a line, bar, or dot chart in
Louvre's look, which no hand-drawn chart should depart from.

- **Line**, for values in order, such as by day. **Bar**, for one value to each label, such as each option's cost;
  give it a `focus`, the label whose bar is in the accent. **Dot**, for each label's values side by side, such as
  before and after.
- **`finding`**: what the chart shows, in a sentence, as its title. "Checkout fell under its target on Thursday",
  not "Checkout latency". **`measure`**: what is measured, and when, under it.
- **The first series is the one the chart is about**, in the accent; up to three more are muted ink, for comparison.
  Each is labeled where it is, so there is no legend: name a series as its label should read, such as "last week".
- **`notes`**: the moments that matter, each on a label. They are numbered on the chart, as Louvre numbers its threads,
  and said in a sentence under it, where a reader can quote them in a comment. One to three; never more than nine.
- **`unit`**, such as "ms" or "%", goes after the largest value on the axis and each value written on the chart.
  **`target`**, on a line chart, is a value to compare with, dotted across it. **`source`** closes the figure.
- Say the chart's finding in the page's text too: a reader who cannot see the chart still has it.
- A chart of a few numbers is better as a table, or as KPIs.

The figure it returns, for a reader of the markup:

```html
<figure class="l-plot">
<figcaption><span class="l-say">The finding</span><span class="l-measure">What is measured</span></figcaption>
<svg class="l-chart" viewBox="0 0 440 196" role="img"><title>The finding. What is measured</title>
<text class="l-name">A row's name</text> <text class="l-label">A series' label</text>
<text class="l-value">A value</text> <text class="l-mark">1</text> ...</svg>
<ol class="l-notes"><li>The first note.</li></ol>
<p class="l-source">Where the numbers come from</p>
</figure>
```

To draw a chart it cannot, such as a map or a diagram, follow the same look by hand: a `figure` of class `l-plot`, an
SVG of class `l-chart` about 440 units wide with its text in the classes above, the accent on what the chart is about
and muted ink and `var(--l-rule)` hairlines for the rest, labels in place of a legend, and a `<title>` that says what
it shows. Color a mark with its `fill` or `stroke` attribute, set to one of the properties above.

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
- No color says anything alone; every chart is drawn by `style_chart`, or follows its look.
- Nothing is wider than a phone; nothing loads from the network.
- No secret, token, or private data is on the page.
