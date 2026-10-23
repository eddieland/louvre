import re
from importlib.metadata import version

import pytest
from fastapi.testclient import TestClient

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
