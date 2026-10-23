import re
from collections.abc import Iterator
from importlib.metadata import version
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from louvre.web import ui
from louvre.web.app import create


@pytest.fixture
def client() -> TestClient:
    return TestClient(create())


def test_landing_links_the_sample_artifact(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert 'href="/a/checkout-latency"' in response.text
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_an_artifact_is_framed_without_same_origin(client: TestClient) -> None:
    response = client.get("/a/checkout-latency")

    assert response.status_code == 200
    frame = re.search(r"<iframe[^>]*>", response.text, re.DOTALL)
    assert frame
    assert 'src="/a/checkout-latency/content"' in frame.group()
    sandbox = re.search(r'sandbox="([^"]*)"', frame.group())
    assert sandbox
    assert "allow-scripts" in sandbox.group(1).split()
    assert "allow-same-origin" not in sandbox.group(1).split()


def test_an_artifacts_html_is_served_sandboxed_even_alone(client: TestClient) -> None:
    response = client.get("/a/checkout-latency/content")

    assert response.status_code == 200
    policy = response.headers["content-security-policy"]
    assert policy.startswith("sandbox allow-scripts ")
    assert "allow-same-origin" not in policy
    assert "default-src 'none'" in policy
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "<svg" in response.text


@pytest.mark.parametrize("path", ["/a/nope", "/a/nope/content", "/a/..%2Fapp.py/content"])
def test_an_unknown_artifact_is_not_found(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


def test_health_names_the_version(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok", "version": version("louvre")}


def test_directions_lists_each_exploration_page(client: TestClient) -> None:
    response = client.get("/directions")

    assert response.status_code == 200
    for name in ("gallery", "margins", "studio"):
        assert f'href="/directions/2026-10-23-directions/{name}"' in response.text
    assert "Louvre: Studio" in response.text


def test_an_exploration_page_is_served_whole(client: TestClient) -> None:
    response = client.get("/directions/2026-10-23-directions/studio")

    assert response.status_code == 200
    assert "<title>Louvre: Studio</title>" in response.text
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


@pytest.mark.parametrize(
    "path",
    ["/directions/2026-10-23-directions/nope", "/directions/nope/studio", "/directions/..%2F..%2Fsrc/app"],
)
def test_an_unknown_exploration_is_not_found(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


def test_the_landing_page_links_the_directions(client: TestClient) -> None:
    assert 'href="/directions"' in client.get("/").text


@pytest.fixture
def built(tmp_path: Path) -> Iterator[Path]:
    """A built UI of two files, where louvre.web.ui looks for one."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>Louvre</title><div id=root></div>", encoding="utf-8")
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    with mock.patch.object(ui, "_CANDIDATES", (tmp_path,)):
        yield tmp_path


def test_the_app_is_its_index_at_every_route(client: TestClient, built: Path) -> None:
    for path in ("/app", "/app/", "/app/a/checkout-latency"):
        response = client.get(path)

        assert response.status_code == 200, path
        assert "<div id=root>" in response.text
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert response.headers["cache-control"] == "no-cache"


def test_a_built_asset_is_served_and_kept(client: TestClient, built: Path) -> None:
    response = client.get("/app/assets/index-abc123.js")

    assert response.status_code == 200
    assert response.text == "console.log(1)"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_a_path_out_of_the_build_serves_the_index_not_the_file(client: TestClient, built: Path) -> None:
    (built.parent / "secret.txt").write_text("not for the web", encoding="utf-8")

    response = client.get("/app/..%2Fsecret.txt")

    assert "not for the web" not in response.text


def test_the_app_says_so_when_it_is_not_built(client: TestClient) -> None:
    with mock.patch.object(ui, "_CANDIDATES", ()):
        response = client.get("/app/")

    assert response.status_code == 503
    assert "make ui-build" in response.text
