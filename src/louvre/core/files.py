"""Files beside a version: what its page shows besides its content, such as images and data (L8, M9).

A version is published with its files, each a path relative to the page, a type, and its bytes, and they are as
immutable as its content. The page names a file by that path (`<img src="p95.png">`), so it reads what it needs
without the network. Its text, and so its anchors, are its content's alone.

A version with files is served under a path of its own, `/content/<artifact>/<n>/<key>/`, its page at the path and
each file under it, and its policy lets it load files from there and nowhere else, so a page reads its own version's
files and never another's. A sandboxed page's requests carry no session, so the key, which only a person who may read
the version learns, is what a request for a file needs (D012). A file's bytes are stored once, by their hash: a new
version that names a file unchanged stores nothing new.

Each file is one of a few types, checked against what it holds, so it is what it says it is. This module knows no
store: the store calls it inside the write that publishes a version (louvre.core.store).
"""

import json
import re
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import assert_never

from louvre.core.db import Connection


class Type(StrEnum):
    """A type of file a version may carry."""

    PNG = "image/png"
    JPEG = "image/jpeg"
    GIF = "image/gif"
    WEBP = "image/webp"
    SVG = "image/svg+xml"
    PDF = "application/pdf"
    WOFF2 = "font/woff2"
    CSV = "text/csv"
    JSON = "application/json"
    TEXT = "text/plain"


@dataclass(frozen=True)
class File:
    """A file beside a version's content."""

    #: Where it is, relative to the page, as the page names it: `p95.png`, or `data/regions.csv`.
    path: str
    content_type: Type
    data: bytes


class FilesError(ValueError):
    """A version's files cannot be published, and why."""

    def __init__(self, message: str, *, too_long: bool = False) -> None:
        """Say why, and whether it is that something is over its bound."""
        super().__init__(message)
        self.too_long = too_long


#: The most bytes one file holds.
MAX_FILE = 2_000_000
#: The most bytes a version's files hold together: within what one request may carry, encoded.
MAX_FILES = 3_000_000
#: The most files a version carries.
MAX_COUNT = 50
#: A file's path: up to four parts, each letters, digits, dots, dashes, and underscores, not starting with a dot.
_PATH = re.compile(r"(?:[A-Za-z0-9_-][A-Za-z0-9._-]{0,99}/){0,3}[A-Za-z0-9_-][A-Za-z0-9._-]{0,99}")
#: How each binary type's file begins.
_MAGIC: Mapping[Type, tuple[bytes, ...]] = {
    Type.PNG: (b"\x89PNG\r\n\x1a\n",),
    Type.JPEG: (b"\xff\xd8\xff",),
    Type.GIF: (b"GIF87a", b"GIF89a"),
    Type.PDF: (b"%PDF-",),
    Type.WOFF2: (b"wOF2",),
}


def check(files: Sequence[File]) -> None:
    """Hold a version's files to their bounds and their types.

    Raises:
        FilesError: Too many files, or too many bytes in one or in all (`too_long`); a path that is not a plain path, or
            one named twice; or a file that is not what its type says.
    """
    if len(files) > MAX_COUNT:
        raise FilesError(f"a version carries at most {MAX_COUNT} files, not {len(files)}", too_long=True)
    for f in files:
        if not _PATH.fullmatch(f.path):
            msg = f"{f.path!r} is not a plain path: up to four parts of letters, digits, dots, dashes, and underscores"
            raise FilesError(msg)
        if len(f.data) > MAX_FILE:
            msg = f"{f.path} holds {len(f.data):,} bytes, over the most a file holds, {MAX_FILE:,}"
            raise FilesError(msg, too_long=True)
        if not _is(f.content_type, f.data):
            raise FilesError(f"{f.path} is not {f.content_type}")
    if len({f.path for f in files}) < len(files):
        raise FilesError("a path is named twice")
    if sum(len(f.data) for f in files) > MAX_FILES:
        raise FilesError(f"a version's files hold at most {MAX_FILES:,} bytes together", too_long=True)


def new_key() -> str:
    """Make the key a version's files are served under.

    Returns:
        A key no one can guess: 128 random bits.
    """
    return secrets.token_urlsafe(16)


def insert(conn: Connection, artifact_id: str, n: int, files: Sequence[File]) -> None:
    """Record a version's files, inside the write that publishes it, each file's bytes once by their hash."""
    for f in files:
        digest = sha256(f.data).hexdigest()
        conn.execute("INSERT INTO blobs (sha256, data) VALUES (%s, %s) ON CONFLICT DO NOTHING", (digest, f.data))
        conn.execute(
            "INSERT INTO files (artifact_id, n, path, content_type, size, sha256) VALUES (%s, %s, %s, %s, %s, %s)",
            (artifact_id, n, f.path, f.content_type.value, len(f.data), digest),
        )


def listed(conn: Connection, artifact_id: str, n: int) -> list[dict[str, object]]:
    """List a version's files.

    Returns:
        Each file's path, type, and size, by path.
    """
    rows = conn.execute(
        "SELECT path, content_type, size FROM files WHERE artifact_id = %s AND n = %s ORDER BY path",
        (artifact_id, n),
    ).fetchall()
    return [{"path": r["path"], "content_type": r["content_type"], "size": r["size"]} for r in rows]


def served(conn: Connection, artifact_id: str, n: int, key: str, path: str) -> tuple[Type, bytes] | None:
    """Find a file by the path it is served at, as Louvre serves it to whoever has the version's key.

    Returns:
        Its type and its bytes, or None when the version has no file at that path, or the key is not its key.
    """
    row = conn.execute(
        "SELECT f.content_type, b.data FROM files f JOIN versions v ON (v.artifact_id, v.n) = (f.artifact_id, f.n)"
        " JOIN blobs b ON b.sha256 = f.sha256 WHERE f.artifact_id = %s AND f.n = %s AND f.path = %s"
        " AND v.files_key = %s",
        (artifact_id, n, path, key),
    ).fetchone()
    if row is None:
        return None
    return Type(str(row["content_type"])), bytes(row["data"])


def _is(content_type: Type, data: bytes) -> bool:
    """Tell whether a file holds what its type says.

    Returns:
        Whether it begins as its binary type's files do, or is text of its kind.
    """
    match content_type:
        case Type.PNG | Type.JPEG | Type.GIF | Type.PDF | Type.WOFF2:
            return data.startswith(_MAGIC[content_type])
        case Type.WEBP:
            return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
        case Type.SVG:
            text = _text(data)
            return text is not None and "<svg" in text
        case Type.JSON:
            try:
                json.loads(data)
            except ValueError:
                return False
            return True
        case Type.CSV | Type.TEXT:
            return _text(data) is not None
        case _:
            assert_never(content_type)


def _text(data: bytes) -> str | None:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None
