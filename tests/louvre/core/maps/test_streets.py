"""Street tiles, fetched from the build OpenFreeMap's TileJSON names, and empty when it is out of reach."""

import io
import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from unittest import mock

from louvre.core.maps import streets
from louvre.core.maps.streets import Streets

#: A TileJSON, as OpenFreeMap's names its current build.
TILEJSON = json.dumps({"tiles": ["https://tiles.example/planet/b1/{z}/{x}/{y}.pbf"]}).encode()


@contextmanager
def site(pages: Mapping[str, bytes], asked: list[str]) -> Iterator[streets.Open]:
    """Serve `pages` by URL, recording each URL asked for in `asked`, and refuse any other.

    Yields:
        How to open a URL there.
    """

    def opened(url: str, timeout: float) -> io.BytesIO:
        assert timeout == streets.TIMEOUT
        asked.append(url)
        if url not in pages:
            raise OSError(url)
        return io.BytesIO(pages[url])

    yield opened


def test_a_tile_is_fetched_from_the_build_the_tilejson_names_which_is_read_once() -> None:
    asked: list[str] = []
    with site(
        {"https://tiles.example/planet": TILEJSON, "https://tiles.example/planet/b1/14/7/9.pbf": b"tile"},
        asked,
    ) as opened:
        found = Streets("https://tiles.example/planet", opened)

        assert found.tile(14, 7, 9) == b"tile"
        assert found.tile(14, 7, 9) == b"tile"

    assert asked == [
        "https://tiles.example/planet",
        "https://tiles.example/planet/b1/14/7/9.pbf",
        "https://tiles.example/planet/b1/14/7/9.pbf",
    ]


def test_the_tilejson_is_read_again_once_it_is_old() -> None:
    asked: list[str] = []
    with (
        site(
            {"https://tiles.example/planet": TILEJSON, "https://tiles.example/planet/b1/0/0/0.pbf": b"t"},
            asked,
        ) as opened,
        mock.patch.object(streets, "REFRESH", -1.0),
    ):
        found = Streets("https://tiles.example/planet", opened)
        found.tile(0, 0, 0)
        found.tile(0, 0, 0)

    assert asked.count("https://tiles.example/planet") == 2


def test_a_tile_out_of_reach_is_empty_and_one_that_cannot_be_is_none() -> None:
    asked: list[str] = []
    with site({}, asked) as opened:
        found = Streets("https://tiles.example/planet", opened)

        assert found.tile(3, 1, 2) == b""
        assert found.tile(15, 0, 0) is None
        assert found.tile(2, 4, 0) is None
        assert found.tile(2, 0, -1) is None
        assert found.tile(-1, 0, 0) is None
        assert Streets("", opened).tile(3, 1, 2) == b""

    assert asked == ["https://tiles.example/planet"]
