"""Checking a page against the house style's guide: what would break in Louvre as errors, the rest as warnings."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from louvre.core import style
from louvre.core.style.check import Rule, Severity, check

#: A page in the house style that follows the guide, with `{}` where a case puts its markup.
PAGE = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Checkout is back under 450 ms</title>
<style>
{style.CSS}</style>
</head>
<body class="louvre">
<main>
<h1>Checkout is back under 450 ms</h1>
<p class="l-lede">The tax quote is cached per cart, so checkout makes one call to the tax service.</p>
<svg class="l-chart" viewBox="0 0 440 200" role="img" aria-label="p95 fell from 1,180 ms to 430 ms">
<polyline fill="none" stroke="var(--l-accent)" points="60,13 420,113"/>
</svg>
{{}}
</main>
</body>
</html>
"""


def found(markup: str, page: str = PAGE) -> set[tuple[Rule, Severity]]:
    """Check `page` with `markup` in it.

    Returns:
        The rule and severity of each finding.
    """
    return {(f.rule, f.severity) for f in check(page.replace("{}", markup))}


def test_a_page_that_follows_the_guide_has_nothing_to_change() -> None:
    assert check(PAGE.replace("{}", "")) == []


@pytest.mark.parametrize("kind", list(style.Kind))
def test_a_starter_page_as_it_is_has_its_words_left_in(kind: style.Kind) -> None:
    findings = check(style.STARTERS[kind])

    assert findings
    assert {(f.rule, f.severity) for f in findings} == {(Rule.PLACEHOLDER, Severity.ERROR)}


@pytest.mark.parametrize(
    ("markup", "rule", "severity"),
    [
        ('<img src="https://example.com/a.png" alt="">', Rule.NETWORK, Severity.ERROR),
        ('<script src="app.js"></script>', Rule.NETWORK, Severity.ERROR),
        ('<link rel="stylesheet" href="//cdn.example.com/x.css">', Rule.NETWORK, Severity.ERROR),
        ('<style>@import "fonts.css";</style>', Rule.NETWORK, Severity.ERROR),
        ('<div style="background: url(https://example.com/y.png)"></div>', Rule.NETWORK, Severity.ERROR),
        ('<script>fetch("/data.json")</script>', Rule.NETWORK, Severity.ERROR),
        ("<script>localStorage.setItem('seen', '1')</script>", Rule.STORAGE, Severity.ERROR),
        ("<button onclick=\"document.cookie = 'a=1'\">Remember</button>", Rule.STORAGE, Severity.ERROR),
        ("<p>One claim to a sentence, so a comment can quote it.</p>", Rule.PLACEHOLDER, Severity.ERROR),
        ("<details><summary>Method</summary><p>How we measured.</p></details>", Rule.HIDDEN, Severity.WARNING),
        ('<img src="data:image/png;base64,iVBORw0KGgo=">', Rule.IMAGE, Severity.WARNING),
        ('<svg viewBox="0 0 10 10"><rect width="10" height="10"/></svg>', Rule.CHART, Severity.WARNING),
        ("<h1>A second title</h1>", Rule.HEADING, Severity.WARNING),
        ("<style>.wide { min-width: 720px; }</style>", Rule.WIDTH, Severity.WARNING),
        ('<p style="color: rgb(20, 20, 20)">Dark text on a dark page</p>', Rule.COLOR, Severity.WARNING),
        ('<svg role="img" aria-label="A bar"><rect fill="#123456"/></svg>', Rule.COLOR, Severity.WARNING),
    ],
)
def test_it_finds_what_goes_against_the_guide(markup: str, rule: Rule, severity: Severity) -> None:
    assert found(markup) == {(rule, severity)}


@pytest.mark.parametrize(
    "markup",
    [
        '<a href="https://example.com/dashboard">The dashboard</a>',
        '<img src="data:image/png;base64,iVBORw0KGgo=" alt="">',
        '<svg aria-hidden="true"><use href="#mark"/></svg>',
        '<svg role="img"><title>Declines rose at submit</title><rect fill="url(#grad)"/></svg>',
        "<details open><summary>Method</summary><p>How we measured.</p></details>",
        "<style>.chart { max-width: 900px; width: 100%; }</style>",
        "<script>let seen = new Set(); document.title</script>",
        '<p class="l-muted">Done</p>',
    ],
)
def test_it_lets_be_what_the_guide_allows(markup: str) -> None:
    assert found(markup) == set()


def test_errors_come_before_warnings() -> None:
    findings = check(PAGE.replace("{}", '<details><summary>a</summary>b</details><img src="https://x/y.png" alt="">'))

    assert [f.severity for f in findings] == [Severity.ERROR, Severity.WARNING]


def test_a_page_of_its_own_look_may_use_its_own_colors_but_not_the_styles_classes_bare() -> None:
    own = '<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
    own += "<title>Mock-up</title><style>body { color: #222; }</style></head><body><h1>Sign in</h1>{}</body></html>"

    assert found("", own) == set()
    assert found('<p class="l-lede">The finding.</p>', own) == {(Rule.STYLESHEET, Severity.ERROR)}


def test_a_fragment_lacks_its_head_and_its_title() -> None:
    findings = check("<p>Just a paragraph.</p>")

    assert [f.rule for f in findings] == [Rule.HEAD, Rule.HEAD, Rule.HEAD, Rule.HEAD, Rule.HEADING]


@given(st.text())
def test_any_text_is_checked_without_raising(page: str) -> None:
    assert all(f.severity in Severity for f in check(page))


def test_a_page_names_its_files_by_their_paths_and_every_file_is_named() -> None:
    named = '<img src="p95.png" alt="p95"><a href="./data/regions.csv?v=1#top">The data</a>'
    loaded_from_files = '<script src="app.js"></script><link rel="stylesheet" href="style.css">'

    assert found(named) == {(Rule.FILE, Severity.ERROR)}
    assert check(PAGE.replace("{}", named), frozenset({"p95.png", "data/regions.csv"})) == []
    assert {
        (f.rule, f.severity, f.excerpt)
        for f in check(PAGE.replace("{}", named), frozenset({"p95.png", "data/regions.csv", "spare.png"}))
    } == {
        (Rule.FILE, Severity.WARNING, "spare.png"),
    }
    assert found(loaded_from_files) == {(Rule.NETWORK, Severity.ERROR)}
    assert found('<script>fetch("data/regions.csv")</script>') == set()
