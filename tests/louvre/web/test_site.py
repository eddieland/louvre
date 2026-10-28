"""A deployment's own words: read from its environment, and its Markdown kept as runs of text, never as markup."""

from urllib.parse import urljoin, urlsplit

from hypothesis import given
from hypothesis import strategies as st

from louvre.web.site import Site, paragraphs


def test_the_owner_s_words_are_read_from_the_environment() -> None:
    site = Site.from_environ(
        {
            "LOUVRE_NAME": "  Acme \n Louvre ",
            "LOUVRE_BANNER": " Internal to Acme. \n",
            "LOUVRE_FOOTER": "Help: #louvre",
            "LOUVRE_SIGN_IN_NOTE": "Use your Acme account.",
            "LOUVRE_TOKENS_NOTE": "One namespace per team.",
        },
    )

    assert site == Site(
        name="Acme Louvre",
        banner="Internal to Acme.",
        footer="Help: #louvre",
        sign_in="Use your Acme account.",
        tokens="One namespace per team.",
    )


def test_unset_the_owner_says_nothing() -> None:
    assert Site.from_environ({}).shown() == {"name": "", "banner": [], "footer": [], "sign_in": [], "tokens": []}


def test_markdown_is_kept_as_runs_of_text_with_their_marks() -> None:
    said = paragraphs("Ask in **#louvre** or _mail_ [the team](mailto:louvre@acme.test), `lvt_` tokens.")

    assert said == [
        [
            {"text": "Ask in "},
            {"text": "#louvre", "strong": True},
            {"text": " or "},
            {"text": "mail", "em": True},
            {"text": " "},
            {"text": "the team", "href": "mailto:louvre@acme.test"},
            {"text": ", "},
            {"text": "lvt_", "code": True},
            {"text": " tokens."},
        ],
    ]


def test_a_blank_line_starts_a_paragraph_and_a_new_line_breaks_one() -> None:
    assert paragraphs("Support: #louvre\nPolicy: the wiki\n\nRun by Platform.") == [
        [{"text": "Support: #louvre\nPolicy: the wiki"}],
        [{"text": "Run by Platform."}],
    ]


def test_markup_headings_and_lists_are_shown_as_their_text() -> None:
    assert paragraphs("<script>alert(1)</script>\n\n# Heading\n\n- item") == [
        [{"text": "<script>alert(1)</script>"}],
        [{"text": "# Heading"}],
        [{"text": "- item"}],
    ]


def test_an_escape_or_an_entity_is_the_character_it_names() -> None:
    assert paragraphs(r"\*not bold\* &amp; &copy;") == [[{"text": "*not bold* & ©"}]]


def test_a_link_goes_only_to_the_web_an_address_or_louvre_s_own_pages() -> None:
    said = paragraphs(
        "[a](https://acme.test/policy) [b](/inbox) [c](//evil.test) [d](javascript:alert(1)) [e](data:text/html,x)",
    )

    assert [run for run in said[0] if "href" in run] == [
        {"text": "a", "href": "https://acme.test/policy"},
        {"text": "b", "href": "/inbox"},
    ]
    assert "".join(str(run["text"]) for run in said[0]) == "a b c [d](javascript:alert(1)) [e](data:text/html,x)"


#: A link's target: any text, and text after the starts a browser could read as another site or a script.
TARGETS = st.text() | st.builds(
    str.__add__,
    st.sampled_from(["/", "//", "/\\", "/\t/", "\\\\", "http:", "HTTPS://", "mailto:", "javascript:", "data:"]),
    st.text(),
)


@given(TARGETS)
def test_a_link_never_leads_to_a_script_or_another_site_s_path(target: str) -> None:
    """Whatever a link names, it is to the web, an address, or a path on Louvre's own host, as a browser reads it."""
    for paragraph in paragraphs(f"[x]({target}) [y](<{target}>)"):
        for run in paragraph:
            href = str(run.get("href", ""))
            if not href:
                continue
            # A browser reads a backslash as a slash, and drops tabs and newlines, before it follows a link.
            read = href.replace("\\", "/").replace("\t", "").replace("\n", "").replace("\r", "")
            resolved = urlsplit(urljoin("https://louvre.test/a/x", read))
            assert resolved.scheme in {"https", "http", "mailto"}
            if not href.lower().startswith(("https:", "http:", "mailto:")):
                assert resolved.netloc == "louvre.test"
