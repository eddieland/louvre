"""The map kit: what an artifact draws a map with, served by Louvre at a version (REQUIREMENTS U9, M10).

`louvre-map-1` is MapLibre GL JS (5.24.0, BSD-3-Clause), a basemap from Natural Earth's public-domain 1:50m data (land,
lakes, borders, and places, built by `scripts/basemap.py`), the Noto Sans glyphs its labels are drawn in (Open Font
License), and Louvre's own `kit.js`, which draws a page's GeoJSON on the basemap in the page's Louvre tokens.
`louvre-map-2` is the same, its `kit.js` letting a reader draw a box on a map to comment on (M12), and `louvre-map-3`'s
lights what a later version changed, and a decision's option's place, pans and zooms to a place when the page asks, and
rings a point read where its reader stood with how sure the reading is (M13). A page loads one script, `map.js`:
MapLibre, its stylesheet, and the kit together. The artifact policy lets a page load the kit's path and nothing else
beyond its own files (D008), so a map in Louvre makes no request outside it.

The kit's files are public, the same for every caller: a sandboxed page's requests carry no session. The version is in
the path, so a later kit is a new path, and never redraws a published map. Each version is a directory beside this
module, holding what it changes; a file it lacks is the version before it's. Louvre serves every version, for as long
as a page may load it; browsers keep each file for a year, so a version once published never changes.
"""

import json
import re
from collections.abc import Mapping, Sequence
from importlib.resources import files
from importlib.resources.abc import Traversable

#: Where Louvre serves every version of the kit, each under its name.
ROOT = "/kit/"
#: The kit's name and version, as a page names it: the version a new page loads.
VERSION = "louvre-map-3"
#: Where Louvre serves the current kit: a page loads `map.js` from here.
PATH = f"{ROOT}{VERSION}/"

_ROOT = files(__name__)
#: The prefix of every version's name, before its number.
_PREFIX = "louvre-map-"
#: Every version of the kit, in order, the current one among them: each directory beside this module named for one.
VERSIONS: Sequence[str] = sorted(
    (d.name for d in _ROOT.iterdir() if d.is_dir() and d.name.startswith(_PREFIX)),
    key=lambda name: int(name.removeprefix(_PREFIX)),
)
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


def served(version: str, path: str) -> tuple[str, bytes] | None:
    """Find the file a version of the kit serves at `path`, under its directory in `ROOT`.

    Returns:
        Its media type and bytes, or None if that version has none there, or there is no such version. A range of
        glyphs the kit does not carry, of a font it does, such as Chinese, is served empty, so a label leaves those
        characters out rather than failing.
    """
    kit = KITS.get(version, {})
    found = kit.get(path)
    glyphs = _GLYPHS.fullmatch(path)
    if found is None and glyphs and f"glyphs/{glyphs['font']}/{_FIRST_RANGE}" in kit:
        start, end = int(glyphs["start"]), int(glyphs["end"])
        if start % 256 == 0 and end == start + 255:
            return _TYPES[".pbf"], b""
    return found


def _read_all() -> dict[str, dict[str, tuple[str, bytes]]]:
    """Read every version's files, each over the version before it's.

    Returns:
        Each version's files, by path under the version's, with each one's media type and bytes.
    """
    kits: dict[str, dict[str, tuple[str, bytes]]] = {}
    before: dict[str, tuple[str, bytes]] = {}
    for version in VERSIONS:
        before = kits[version] = _read(version, before)
    return kits


def _read(version: str, before: Mapping[str, tuple[str, bytes]]) -> dict[str, tuple[str, bytes]]:
    """Read every file a version of the kit serves: its own, and the version before it's that it lacks.

    Returns:
        Each file by its path under the version's, with its media type and bytes.
    """
    found = dict(before)
    found["map.js"] = (_TYPES[".js"], _script(version))
    for folder in ("basemap", "glyphs"):
        if not (_ROOT / version / folder).is_dir():
            continue
        for item in (_ROOT / version / folder).iterdir():
            for leaf in item.iterdir() if item.is_dir() else [item]:
                path = f"{folder}/{item.name}/{leaf.name}" if item.is_dir() else f"{folder}/{item.name}"
                found[path] = (_TYPES[leaf.name[leaf.name.rindex(".") :]], leaf.read_bytes())
    found["maplibre-gl-LICENSE.txt"] = (_TYPES[".txt"], _file(version, "maplibre-gl-LICENSE.txt").read_bytes())
    return found


def _script(version: str) -> bytes:
    """Put a version's MapLibre, its stylesheet, and its kit in one script.

    Returns:
        The script.
    """
    maplibre = _file(version, "maplibre-gl.js").read_text(encoding="utf-8")
    css = _file(version, "maplibre-gl.css").read_text(encoding="utf-8")
    kit = _file(version, "kit.js").read_text(encoding="utf-8").replace(_SLOT, json.dumps(css), 1)
    return f"{maplibre}\n{kit}".encode()


def _file(version: str, name: str) -> Traversable:
    """Find a file of a version's: its own, or the nearest version before it's.

    Returns:
        The file.

    Raises:
        FileNotFoundError: No version up to this one has it.
    """
    for earlier in reversed(VERSIONS[: VERSIONS.index(version) + 1]):
        if (_ROOT / earlier / name).is_file():
            return _ROOT / earlier / name
    raise FileNotFoundError(f"no version of the kit up to {version} has {name}")


#: Every version's files, by version and path under the version's: each one's media type and bytes.
KITS: Mapping[str, Mapping[str, tuple[str, bytes]]] = _read_all()
#: The current kit's files, by path under `PATH`.
FILES = KITS[VERSION]
