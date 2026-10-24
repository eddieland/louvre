"""Street tiles for the map kit: OpenStreetMap's streets, water, and buildings, from OpenFreeMap, passed on by Louvre.

A page's map loads nothing but Louvre (D008), so Louvre fetches each street tile the map asks for from OpenFreeMap
(free, with no key, OpenMapTiles' schema to zoom 14) and answers with it from the kit's path. OpenFreeMap's tiles sit
under a build's name, which changes as it rebuilds the planet: its TileJSON names the current one, read once an hour.
When OpenFreeMap cannot be reached, a tile is answered as empty, and the map shows plain ground where its streets
would be, as it does past the basemap's scale without them.
"""

import json
import logging
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from types import TracebackType
from typing import Protocol, Self

#: OpenFreeMap's TileJSON for the planet, which names where its tiles are.
OPENFREEMAP = "https://tiles.openfreemap.org/planet"
#: The highest zoom OpenFreeMap has tiles for; a map zoomed in past it draws its zoom-14 tiles larger.
MAX_ZOOM = 14
#: How long the tiles' address is kept before the TileJSON is read again, in seconds.
REFRESH = 3600.0
#: How long a request to OpenFreeMap may take, in seconds.
TIMEOUT = 10.0
#: Who asks, as OpenFreeMap reads it: it refuses urllib's own name.
USER_AGENT = "Louvre (+https://github.com/eddieland/louvre)"

_log = logging.getLogger(__name__)


class _Response(Protocol):
    def read(self) -> bytes: ...
    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
        /,
    ) -> bool | None: ...


#: Opens a URL with a timeout, as `urllib.request.urlopen` does.
type Open = Callable[[str, float], _Response]


def _urlopen(url: str, timeout: float) -> _Response:
    # Only ever the TileJSON's URL, and the tiles' it names: https, never a file a caller chose.
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
    return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310


@dataclass
class Streets:
    """Street tiles from a TileJSON's source, such as OpenFreeMap's, kept with the tiles' address it last read."""

    #: The TileJSON's URL; empty for none, so every tile is empty.
    tilejson: str = OPENFREEMAP
    #: How a URL is opened: urllib's, unless a test says otherwise.
    open: Open = _urlopen
    #: The tiles' address, with `{z}`, `{x}`, and `{y}`, and when it was read, by the monotonic clock.
    _template: str = field(default="", init=False)
    _read_at: float = field(default=-REFRESH, init=False)

    def tile(self, z: int, x: int, y: int) -> bytes | None:
        """Fetch the tile at `z`, `x`, `y`.

        Returns:
            The tile, empty when there is no source or it cannot be reached, or None if there is no such tile.
        """
        if not (0 <= z <= MAX_ZOOM and 0 <= x < 2**z and 0 <= y < 2**z):
            return None
        if not self.tilejson:
            return b""
        try:
            return self._fetch(self._address(), z, x, y)
        except (OSError, ValueError, KeyError, IndexError):
            _log.warning("street tile %s/%s/%s could not be fetched", z, x, y, exc_info=True)
            return b""

    def _address(self) -> str:
        if not self._template or time.monotonic() - self._read_at > REFRESH:
            with self.open(self.tilejson, TIMEOUT) as response:
                self._template = str(json.loads(response.read())["tiles"][0])
            self._read_at = time.monotonic()
        return self._template

    def _fetch(self, template: str, z: int, x: int, y: int) -> bytes:
        url = template.replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))
        with self.open(url, TIMEOUT) as response:
            return response.read()
