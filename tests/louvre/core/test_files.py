"""Files beside a version: published with it, held to their types and bounds, and served by its key alone."""

import re
from collections.abc import Callable

import pytest

from louvre.core import files
from louvre.core.db import Connection
from louvre.core.files import MAX_COUNT, MAX_FILE, MAX_FILES, File, FilesError, Type
from louvre.core.store import Code, Refused, Store
from tests.conftest import MakeAgent

#: The smallest PNG: one transparent pixel.
PIXEL = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082",
)
#: A page that names its files.
PAGE = '<h1>p95</h1><img src="p95.png" alt="p95 by day"><a href="data/regions.csv">The data</a>'
#: Its files.
FILES = (File("p95.png", Type.PNG, PIXEL), File("data/regions.csv", Type.CSV, b"region,p95\nus-east,410\n"))


def refused(code: Code, call: Callable[[], object]) -> None:
    """Call `call`, and hold it to being refused with `code`."""
    with pytest.raises(Refused) as caught:
        call()
    assert caught.value.code == code


def publish(store: Store, version_files: tuple[File, ...] = FILES, artifact_id: str | None = None) -> tuple[str, int]:
    """Publish PAGE with `version_files` beside it.

    Returns:
        The artifact's id and the version's number.
    """
    made = store.publish(
        title="p95",
        content_type="text/html",
        content=PAGE,
        artifact_id=artifact_id,
        files=version_files,
    )
    return str(made["artifact_id"]), int(str(made["version"]))


def test_a_versions_files_are_served_by_its_key_alone(conn: Connection, agent: MakeAgent) -> None:
    store = agent()
    artifact, n = publish(store)
    key = store.files_key(artifact, n)
    assert key is not None

    assert files.served(conn, artifact, n, key, "p95.png") == (Type.PNG, PIXEL)
    assert files.served(conn, artifact, n, key, "data/regions.csv") == (Type.CSV, FILES[1].data)
    assert files.served(conn, artifact, n, "not-its-key", "p95.png") is None
    assert files.served(conn, artifact, n, key, "other.png") is None
    assert files.listed(conn, artifact, n) == [
        {"path": "data/regions.csv", "content_type": "text/csv", "size": 23},
        {"path": "p95.png", "content_type": "image/png", "size": len(PIXEL)},
    ]


def test_a_version_without_files_has_no_key_and_its_text_is_its_contents_alone(agent: MakeAgent) -> None:
    store = agent()
    plain = store.publish(title="Plain", content_type="text/html", content=PAGE)
    artifact, n = publish(store)

    assert store.files_key(str(plain["artifact_id"]), 1) is None
    assert store.read(artifact, n)["text"] == store.read(str(plain["artifact_id"]), 1)["text"]


def test_a_new_version_replaces_a_file_and_the_old_keeps_its_own(conn: Connection, agent: MakeAgent) -> None:
    store = agent()
    artifact, first = publish(store)
    redrawn = File("p95.png", Type.PNG, PIXEL + b"\x00")
    _, second = publish(store, (redrawn, FILES[1]), artifact)
    first_key, second_key = store.files_key(artifact, first), store.files_key(artifact, second)
    assert first_key is not None
    assert second_key is not None

    assert first_key != second_key
    assert files.served(conn, artifact, first, first_key, "p95.png") == (Type.PNG, PIXEL)
    assert files.served(conn, artifact, second, second_key, "p95.png") == (Type.PNG, redrawn.data)
    assert files.served(conn, artifact, second, first_key, "p95.png") is None
    # The unchanged CSV is stored once, for both versions.
    assert conn.execute("SELECT count(*) AS n FROM blobs").fetchone() == {"n": 3}


@pytest.mark.parametrize(
    ("content_type", "data"),
    [
        (Type.JPEG, b"\xff\xd8\xff\xe0rest"),
        (Type.GIF, b"GIF89a rest"),
        (Type.WEBP, b"RIFF\x00\x00\x00\x00WEBPVP8 "),
        (Type.PDF, b"%PDF-1.7 rest"),
        (Type.WOFF2, b"wOF2rest"),
        (Type.SVG, b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'),
        (Type.JSON, b'{"p95": [410, 470]}'),
        (Type.TEXT, "Notes \N{EM DASH} in UTF-8.".encode()),
    ],
)
def test_each_type_is_taken_when_the_file_is_one(content_type: Type, data: bytes) -> None:
    files.check([File("file", content_type, data)])


@pytest.mark.parametrize(
    ("given", "says"),
    [
        ([File("a.jpg", Type.JPEG, PIXEL)], "is not image/jpeg"),
        ([File("a.png", Type.PNG, b"<html>not an image</html>")], "is not image/png"),
        ([File("a.svg", Type.SVG, b"<html><script>alert(1)</script></html>")], "is not image/svg+xml"),
        ([File("a.json", Type.JSON, b"{not json")], "is not application/json"),
        ([File("a.csv", Type.CSV, b"\xff\xfe not utf-8")], "is not text/csv"),
        ([File("../secret.png", Type.PNG, PIXEL)], "not a plain path"),
        ([File("/root.png", Type.PNG, PIXEL)], "not a plain path"),
        ([File(".hidden", Type.TEXT, b"x")], "not a plain path"),
        ([File("a/b/c/d/e.txt", Type.TEXT, b"x")], "not a plain path"),
        ([File("a.png", Type.PNG, PIXEL), File("a.png", Type.PNG, PIXEL)], "named twice"),
    ],
)
def test_files_that_are_not_what_they_say_or_where_are_refused(given: list[File], says: str) -> None:
    with pytest.raises(FilesError, match=re.escape(says)) as caught:
        files.check(given)
    assert caught.value.too_long is False


@pytest.mark.parametrize(
    "given",
    [
        [File("big.txt", Type.TEXT, b"x" * (MAX_FILE + 1))],
        [File(f"{i}.txt", Type.TEXT, b"x" * MAX_FILE) for i in range(MAX_FILES // MAX_FILE + 1)],
        [File(f"{i}.txt", Type.TEXT, b"x") for i in range(MAX_COUNT + 1)],
    ],
)
def test_files_over_their_bounds_are_too_long(given: list[File]) -> None:
    with pytest.raises(FilesError) as caught:
        files.check(given)
    assert caught.value.too_long is True


def test_the_store_refuses_files_it_cannot_publish_with_a_code_and_publishes_nothing(
    conn: Connection,
    agent: MakeAgent,
) -> None:
    store = agent()

    refused(Code.INVALID, lambda: publish(store, (File("a.png", Type.PNG, b"no"),)))
    refused(Code.TOO_LONG, lambda: publish(store, (File("big.txt", Type.TEXT, b"x" * (MAX_FILE + 1)),)))
    assert conn.execute("SELECT count(*) AS n FROM versions").fetchone() == {"n": 0}
