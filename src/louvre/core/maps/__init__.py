"""The map kit: what an artifact draws a map with, served by Louvre at a version (REQUIREMENTS U9, M10).

`louvre-map-1` is MapLibre GL JS (5.24.0, BSD-3-Clause), a basemap from Natural Earth's public-domain 1:50m data
(land, lakes, borders, and places, built by `scripts/basemap.py`), the Noto Sans glyphs its labels are drawn in (Open
Font License), and Louvre's own `kit.js`, which draws a page's GeoJSON on the basemap in the page's Louvre tokens. A
page loads one script, `map.js`: MapLibre, its stylesheet, and the kit together. The artifact policy lets a page load
the kit's path and nothing else beyond its own files (D008), so a map in Louvre makes no request outside it.

The kit's files are public, the same for every caller: a sandboxed page's requests carry no session. The version is in
the path, so a later kit is a new path, and never redraws a published map.
"""

import json
import re
from collections.abc import Mapping
from importlib.resources import files

#: The kit's name and version, as a page names it.
VERSION = "louvre-map-1"
#: Where Louvre serves the kit: a page loads `map.js` from here.
PATH = f"/kit/{VERSION}/"

_FILES = files(__name__) / VERSION
#: Where `kit.js` takes MapLibre's stylesheet, as a JavaScript string.
_SLOT = '/* maplibre-gl.css */ ""'
#: Each kind of file the kit serves, by its suffix, and its media type.
_TYPES: Mapping[str, str] = {
    ".js": "text/javascript",
    ".json": "application/json",
    ".pbf": "application/x-protobuf",
    ".txt": "text/plain",
}
#: A range of a font's glyphs, as MapLibre asks for one: 256 code points from a multiple of 256.
_GLYPHS = re.compile(r"glyphs/(?P<font>[^/]+)/(?P<start>\d+)-(?P<end>\d+)\.pbf")
#: The range of glyphs every font the kit carries has.
_FIRST_RANGE = "0-255.pbf"


def served(path: str) -> tuple[str, bytes] | None:
    """Find the file the kit serves at `path`, under `PATH`.

    Returns:
        Its media type and bytes, or None if the kit has none there. A range of glyphs the kit does not carry, of a
        font it does, such as Chinese, is served empty, so a label leaves those characters out rather than failing.
    """
    found = FILES.get(path)
    glyphs = _GLYPHS.fullmatch(path)
    if found is None and glyphs and f"glyphs/{glyphs['font']}/{_FIRST_RANGE}" in FILES:
        start, end = int(glyphs["start"]), int(glyphs["end"])
        if start % 256 == 0 and end == start + 255:
            return _TYPES[".pbf"], b""
    return found


def _script() -> bytes:
    """Put MapLibre, its stylesheet, and the kit in one script.

    Returns:
        The script.
    """
    maplibre = (_FILES / "maplibre-gl.js").read_text(encoding="utf-8")
    css = (_FILES / "maplibre-gl.css").read_text(encoding="utf-8")
    kit = (_FILES / "kit.js").read_text(encoding="utf-8").replace(_SLOT, json.dumps(css), 1)
    return f"{maplibre}\n{kit}".encode()


def _read() -> dict[str, tuple[str, bytes]]:
    """Read every file the kit serves.

    Returns:
        Each file by its path under the kit's, with its media type and bytes.
    """
    found: dict[str, tuple[str, bytes]] = {"map.js": (_TYPES[".js"], _script())}
    for folder in ("basemap", "glyphs"):
        for item in (_FILES / folder).iterdir():
            for leaf in item.iterdir() if item.is_dir() else [item]:
                path = f"{folder}/{item.name}/{leaf.name}" if item.is_dir() else f"{folder}/{item.name}"
                found[path] = (_TYPES[leaf.name[leaf.name.rindex(".") :]], leaf.read_bytes())
    found["maplibre-gl-LICENSE.txt"] = (_TYPES[".txt"], (_FILES / "maplibre-gl-LICENSE.txt").read_bytes())
    return found


#: Every file the kit serves, by its path under `PATH`: its media type and its bytes.
FILES: Mapping[str, tuple[str, bytes]] = _read()
