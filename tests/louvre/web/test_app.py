"""The app's own pages: the web UI at every path it routes, the design study, and health."""

import re
from collections.abc import Iterator
from importlib.metadata import version
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from louvre.core import style
from louvre.web import ui
from louvre.web.app import ARTIFACT_POLICY, create, with_bridge
from tests.conftest import web_settings


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A client of an app with no database, which its pages do not need."""
    with TestClient(create(web_settings(None))) as found:
        yield found


def test_health_names_the_version(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok", "version": version("louvre")}


def test_directions_lists_each_exploration_page(client: TestClient) -> None:
    response = client.get("/directions")

    assert response.status_code == 200
    for name in ("gallery", "margins", "studio"):
        assert f'href="/directions/2026-10-23-directions/{name}"' in response.text
    assert "Louvre: Studio" in response.text
    assert 'href="/directions/board"' in response.text


def test_an_exploration_page_is_served_whole(client: TestClient) -> None:
    response = client.get("/directions/2026-10-23-directions/studio")

    assert response.status_code == 200
    assert "<title>Louvre: Studio</title>" in response.text
    # Framed by Louvre alone: the design study's board shows it.
    assert "frame-ancestors 'self'" in response.headers["content-security-policy"]


def test_the_design_study_is_a_board_with_no_database(client: TestClient) -> None:
    board = client.get("/api/directions/board").json()

    assert board["board"]["title"] == "Design study, 2026-10-23"
    assert [(f["id"], f["title"], f["src"]) for f in board["frames"]][:2] == [
        ("gallery-laptop", "Direction: Gallery", "/directions/2026-10-23-directions/gallery"),
        ("gallery-phone", "Direction: Gallery", "/directions/2026-10-23-directions/gallery"),
    ]
    assert len(board["frames"]) == 6
    assert all(client.get(f["src"]).status_code == 200 for f in board["frames"])


@pytest.mark.parametrize(
    "path",
    ["/directions/2026-10-23-directions/nope", "/directions/nope/studio", "/directions/..%2F..%2Fsrc/app"],
)
def test_an_unknown_exploration_is_not_found(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


@pytest.fixture
def built(tmp_path: Path) -> Iterator[Path]:
    """A built UI of two files and the bridge, where louvre.web.ui looks for one."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "bridge").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>Louvre</title><div id=root></div>", encoding="utf-8")
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "bridge" / "bridge.js").write_text("console.log('bridge')", encoding="utf-8")
    with mock.patch.object(ui, "_CANDIDATES", (tmp_path,)):
        yield tmp_path


@pytest.mark.parametrize("path", ["/", "/a/a_123", "/tokens", "/a/a_123?v=2", "/directions/board"])
def test_the_app_is_its_index_at_every_route(client: TestClient, built: Path, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 200, path
    assert "<div id=root>" in response.text
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-cache"


def test_the_old_app_path_moves_to_the_root(client: TestClient) -> None:
    response = client.get("/app/a/a_123", follow_redirects=False)

    assert response.status_code == 308
    assert response.headers["location"] == "/a/a_123"


def test_a_built_asset_is_served_and_kept(client: TestClient, built: Path) -> None:
    response = client.get("/assets/index-abc123.js")

    assert response.status_code == 200
    assert response.text == "console.log(1)"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_a_path_out_of_the_build_serves_the_index_not_the_file(client: TestClient, built: Path) -> None:
    (built.parent / "secret.txt").write_text("not for the web", encoding="utf-8")

    response = client.get("/..%2Fsecret.txt")

    assert "not for the web" not in response.text


def test_the_app_says_so_when_it_is_not_built(client: TestClient) -> None:
    with mock.patch.object(ui, "_CANDIDATES", ()):
        response = client.get("/")

    assert response.status_code == 503
    assert "make ui-build" in response.text


def test_the_bridge_is_read_from_the_build(built: Path) -> None:
    assert ui.bridge() == "console.log('bridge')"
    with mock.patch.object(ui, "_CANDIDATES", ()):
        assert ui.bridge() is None


def test_a_page_without_a_built_bridge_is_served_as_it_is() -> None:
    assert with_bridge("<p>Hi</p>", None) == "<p>Hi</p>"
    assert re.fullmatch(r"<p>Hi</p>\n<script>x</script>\n", with_bridge("<p>Hi</p>", "x"))


def test_the_house_styles_fonts_are_served_to_any_origin_and_kept(client: TestClient) -> None:
    for name, font in style.FONTS.items():
        response = client.get(style.FONTS_PATH + name)

        assert response.status_code == 200
        assert response.content == font
        assert response.headers["content-type"] == "font/woff2"
        assert response.headers["access-control-allow-origin"] == "*"
        assert "immutable" in response.headers["cache-control"]


@pytest.mark.parametrize(
    "path",
    [
        "/style/louvre-1/fonts/nope.woff2",
        "/style/louvre-0/fonts/fraunces.woff2",
        "/style/louvre-1/fonts/fraunces-OFL.txt",
    ],
)
def test_nothing_but_the_house_styles_fonts_is_served_there(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


def test_an_artifact_loads_fonts_only_from_data_urls_and_louvre() -> None:
    assert [d for d in ARTIFACT_POLICY.split("; ") if d.startswith("font-src")] == ["font-src data: 'self'"]
