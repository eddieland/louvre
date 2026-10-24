"""Build the map kit's basemap from Natural Earth's public-domain GeoJSON (louvre.core.maps, REQUIREMENTS U9).

It reads each layer's file from DIR, as Natural Earth's own repository has it (github.com/nvkelso/natural-earth-vector,
`geojson/`), and writes it beside the kit, smaller: coordinates to three decimals, about a hundred metres, as fine as
the 1:50m data is, points that rounding made the same dropped, and every property but those the kit's style reads.

    uv run python scripts/basemap.py DIR
"""

import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import click

#: Where the kit's basemap goes.
OUT = Path(__file__).resolve().parents[1] / "src" / "louvre" / "core" / "maps" / "louvre-map-1" / "basemap"
#: Each layer: its file in the kit, Natural Earth's file, and the properties the kit's style reads.
LAYERS = (
    ("land.json", "ne_50m_land.geojson", ()),
    ("lakes.json", "ne_50m_lakes.geojson", ()),
    ("borders.json", "ne_50m_admin_0_boundary_lines_land.geojson", ()),
    ("places.json", "ne_50m_populated_places_simple.geojson", ("name", "scalerank")),
)
#: Decimals a coordinate keeps.
DECIMALS = 3


@click.command()
@click.argument("source", type=click.Path(exists=True, file_okay=False, path_type=Path))
def main(source: Path) -> None:
    """Write each layer of the basemap from Natural Earth's files in SOURCE."""
    OUT.mkdir(parents=True, exist_ok=True)
    for name, natural_earth, keep in LAYERS:
        read = json.loads((source / natural_earth).read_text(encoding="utf-8"))
        features = [
            {
                "type": "Feature",
                "properties": {k: f["properties"][k] for k in keep},
                "geometry": {"type": f["geometry"]["type"], "coordinates": _round(f["geometry"]["coordinates"])},
            }
            for f in read["features"]
            if f.get("geometry")
        ]
        written = json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":"))
        (OUT / name).write_text(written + "\n", encoding="utf-8")


def _round(coordinates: object) -> object:
    match coordinates:
        case [float() | int(), float() | int(), *_]:
            return [round(float(c), DECIMALS) for c in coordinates[:2]]
        case [[float() | int(), *_], *_]:
            return list(_distinct([_round(c) for c in coordinates]))
        case list():
            return [_round(c) for c in coordinates]
        case _:
            return coordinates


def _distinct(points: Sequence[object]) -> Iterator[object]:
    """Drop each point the same as the one before it, keeping a ring's closing point.

    Yields:
        The points.
    """
    for i, point in enumerate(points):
        if i == 0 or point != points[i - 1] or i == len(points) - 1:
            yield point


if __name__ == "__main__":
    main()
