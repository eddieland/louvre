from louvre.core import render, style


def test_html_is_shown_as_its_author_wrote_it() -> None:
    page = "<!doctype html><p onclick='x()'>Mine</p>"

    assert render.page("text/html", page, "Title") == page


def test_markdown_is_rendered_in_the_house_style() -> None:
    page = render.page("text/markdown", "# Findings\n\n| a | b |\n|---|---|\n| 1 | 2 |\n", "Report <1>")

    assert "<h1>Findings</h1>" in page
    assert "<table>" in page
    assert style.CSS in page
    assert '<body class="louvre">' in page
    assert "<title>Report &lt;1&gt;</title>" in page


def test_markdown_cannot_put_markup_or_scripts_in_its_page() -> None:
    page = render.page("text/markdown", "<script>alert(1)</script>\n\n[x](javascript:alert(1))", "T")

    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page
    assert 'href="javascript:' not in page


def test_a_markdown_versions_text_is_its_pages() -> None:
    assert render.text_of("text/markdown", "# Title\n\nSome *words* here.") == "Title Some words here."
