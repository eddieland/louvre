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
| `map` | Where something is: regions, sites, a route | A map drawn by the map kit, with notes, and a table of its places |

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

To draw a chart it cannot, such as a diagram, follow the same look by hand: a `figure` of class `l-plot`, an
SVG of class `l-chart` about 440 units wide with its text in the classes above, the accent on what the chart is about
and muted ink and `var(--l-rule)` hairlines for the rest, labels in place of a legend, and a `<title>` that says what
it shows. Color a mark with its `fill` or `stroke` attribute, set to one of the properties above.

## Maps

Louvre serves a map kit, `louvre-map-2`: a basemap of land, borders, and cities, drawn in the page's colors, dark and
light, with your places over it. Load its one script in `<head>`, and draw in a `<div class="l-map">` inside a figure
of class `l-plot`, as the `map` starter does:

```html
<script src="/kit/louvre-map-2/map.js"></script>
...
<div class="l-map" id="map" role="img" aria-label="What the map shows, naming each place"></div>
<p class="l-key"><span class="l-focus">What the accent marks</span><span>What the rest are</span></p>
...
<p class="l-source">Where the places come from. Basemap: Natural Earth; streets © OpenStreetMap contributors.</p>
<script>
LouvreMap.draw("map", { data: { type: "FeatureCollection", features: [...] } });
</script>
```

- **`data`** is GeoJSON, with longitude before latitude: points for sites or poles, lines for routes or a vehicle's
  trace, polygons for regions or blocks, each with its parts if it has several. It may instead be a file published
  beside the page, by its path: `data: "places.json"`.
- **The basemap** is Natural Earth's land, borders, and cities from the whole earth down to a city, and
  OpenStreetMap's streets, water, and buildings from there down to a few streets, which Louvre passes on from
  OpenFreeMap. It is quiet, in the page's colors, so the data is what a reader sees.
- **`context`**, GeoJSON or a file too, is what you know that the basemap does not: lanes, kerbs, a site's own paths,
  drawn quietly under the data, as its streets are.
- **`focus`**: give the place the map is about `"focus": true` in its properties, and it is in the accent; the rest
  are muted ink. With no `focus` anywhere, every place is in the accent.
- **`name`** labels each feature on the map once: a point beside it, a line at its middle, an area at its centre;
  `label` names another property to label with instead. A label with no room is left off; the page's table has it.
- **`mark`**: a number, as `"mark": 1`, numbers a place as a chart's note is numbered; say each in the figure's
  `l-notes`, under the map.
- **The key**, `<p class="l-key">` under the map, says what the accent marks, in a `<span class="l-focus">`, and what
  the muted rest are, in a `<span>`, each beside the mark the map draws for it.
- **`ramp`**, as `ramp: { property: "p95", min: 120, max: 940 }`, colors every feature by one numeric property, from
  the muted ink at `min` to the accent at `max`, in place of `focus`. Its key is
  `<span class="l-ramp">p95: 120&nbsp;ms<i></i>940&nbsp;ms</span>`, the bar between its ends.
- **`popups: true`** shows a feature's properties when a reader taps it.
- **Data alone**: publish GeoJSON with `map_publish`, and Louvre draws this page for you: the map, its key, and each
  feature's label and properties under it in an `<ol class="l-features">`, which people comment on. Write HTML only
  when the map is one part of a page.
- **The basemap's credit**, "Basemap: Natural Earth; streets © OpenStreetMap contributors.", goes in the figure's
  `l-source`, as OpenStreetMap's license asks; the map shows it too, folded into its button on a phone.
- The map fits its data, from the whole earth down to a few streets (`maxZoom`, 17 unless said), with a scale bar. A
  reader may pan and zoom it, with two fingers on a phone, or the buttons.
- One map to a page, with every place on it. Each map holds a WebGL context, of which a phone keeps few: the kit
  draws a map while it is in view, and on a phone keeps one drawn at a time.
- A map is a picture: say what it shows in the lede, the figure's finding, its `aria-label`, and a table of its
  places, so a reader who cannot see it, or quote it, still has it.
- A map of a building's floor is not for the kit: draw it as a diagram.

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
stylesheet, font, script, or image. The map kit's script, which Louvre serves, is the one script a page may load.

- The style's own faces load from Louvre, so a page in the style is set as Louvre's own pages are. Shown anywhere
  else, it falls back to the reader's own serif and sans.
- An image, a font, or the data behind a chart is a file beside the page: publish the page with `files_publish`, its
  files with it, and name each by its path, as `<img src="p95.png">`, a CSS `url(p95.png)`, a link, or a script's
  `fetch("data/regions.csv")`. A page loads its own version's files and nothing else. A small image may instead go
  inline: SVG markup, or a `data:` URL.
- Any other font is a file beside the page, or goes inline as a `data:` URL.
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
- Nothing is wider than a phone; nothing loads from the network but the map kit.
- No secret, token, or private data is on the page.
