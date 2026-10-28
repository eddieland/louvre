"""GeoJSON as an artifact (REQUIREMENTS U9, M11): an agent publishes data, and Louvre draws it as a map in its style.

A version's content is a GeoJSON FeatureCollection, or one Feature (RFC 7946: longitude before latitude, in WGS 84).
How it is drawn is declared in a foreign member, `louvre`, which RFC 7946 allows beside the data: the property that
labels a feature, the features the map is about, a ramp of one numeric property, and the key's words. Louvre renders
it as a page in the house style: the map, drawn by the map kit (louvre.core.maps), and under it every feature's label
and properties in the data's order. Those are the page's words, which a thread is anchored on, as on any artifact;
tapping a feature on the map shows them too.
"""

import html
import json
import math
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, assert_never

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, ValidationError

from louvre.core import maps, style

#: The content type, as RFC 7946 registers it.
GEOJSON = "application/geo+json"
#: The most features a version may have: each is a row of the page under the map, which a reader scrolls.
MAX_FEATURES = 2_000
#: The geometry types RFC 7946 has, and how deep each one's positions are nested.
_DEPTH: Mapping[str, int] = {
    "Point": 0,
    "MultiPoint": 1,
    "LineString": 1,
    "MultiLineString": 2,
    "Polygon": 2,
    "MultiPolygon": 3,
}
#: Properties the map kit reads, which are not shown among a feature's properties.
_KIT_PROPERTIES = frozenset({"focus", "mark"})
#: How many numbers a position has: longitude and latitude, and an altitude if it has one.
_POSITION = frozenset({2, 3})
#: The furthest a longitude and a latitude reach from zero, in degrees.
_LONGITUDE = 180.0
_LATITUDE = 90.0
#: How many numbers a box has: its west, south, east, and north.
_BOX = 4
#: The least and the most a point's accuracy may be, in metres: a reading less sure than this says nothing of a place.
_LEAST_ACCURACY = 1
MAX_ACCURACY = 50_000
#: The earth's mean radius, in metres, as a feature's move is measured on it.
_EARTH = 6_371_008.8
#: The eight ways a feature moves, clockwise from north, as a change says it.
_TOWARD = ("north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west")
#: How many features' labels the map's description for a screen reader names, before "and more".
_NAMED = 10
#: The basemap's credit, under the map, as the house style's guide has it.
_CREDIT = "Basemap: Natural Earth; streets © OpenStreetMap contributors."

type Value = StrictStr | StrictInt | StrictFloat | StrictBool


class GeodataError(ValueError):
    """GeoJSON that cannot be published, and why."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Focus(_Model):
    """The features the map is about: those whose `property` is one of `equals`."""

    property: StrictStr
    equals: Annotated[tuple[Value, ...], Field(min_length=1)]


class Ramp(_Model):
    """One numeric property, colored from the muted ink at its least to the accent at its most."""

    property: StrictStr
    #: Its unit, such as "ms" or "%", written after each end of the key.
    unit: StrictStr = ""


class Key(_Model):
    """The key's words: what the accent marks, and what the rest are."""

    focus: StrictStr
    rest: StrictStr = ""


class Look(_Model):
    """How a version's map is drawn: the `louvre` member of its GeoJSON."""

    #: The finding, in a sentence or two, shown as the page's lede.
    description: StrictStr = ""
    #: The property that labels each feature.
    label: StrictStr = "name"
    focus: Focus | None = None
    ramp: Ramp | None = None
    key: Key | None = None


def check(content: str) -> tuple[list[Mapping[str, object]], Look]:
    """Check that `content` is GeoJSON Louvre draws, and read it.

    Returns:
        Its features, in order, and how it is drawn.

    Raises:
        GeodataError: It is not JSON, not a FeatureCollection or a Feature, has a geometry RFC 7946 does not allow,
            a position off the earth, more than `MAX_FEATURES` features, or a `louvre` member Louvre cannot read.
    """
    try:
        data = json.loads(content)
    except ValueError:
        raise GeodataError("not JSON") from None
    if not isinstance(data, dict):
        raise GeodataError("GeoJSON is an object: a FeatureCollection, or a Feature")
    match data.get("type"):
        case "FeatureCollection":
            features = data.get("features")
            if not isinstance(features, list):
                raise GeodataError("a FeatureCollection's features are a list")
        case "Feature":
            features = [data]
        case _:
            raise GeodataError("GeoJSON here is a FeatureCollection, or a Feature")
    if len(features) > MAX_FEATURES:
        raise GeodataError(f"{len(features):,} features, over {MAX_FEATURES:,}: draw fewer, or simplify them")
    checked = [_feature(feature, f"features[{i}]") for i, feature in enumerate(features)]
    try:
        look = Look.model_validate(data.get("louvre") or {})
    except ValidationError as e:
        raise GeodataError(f"its louvre member: {e.errors()[0]['msg']} at {_where(e)}") from None
    return checked, look


def page(content: str, title: str) -> str:
    """Make the page a GeoJSON version is shown as: its map, then each feature's label and properties.

    Returns:
        A whole HTML document in the house style, which draws the map with the kit.
    """
    features, look = check(content)
    labels = [_label(feature, look, i) for i, feature in enumerate(features)]
    drawn = {"type": "FeatureCollection", "features": list(_drawn(features, look))}
    options = {"data": drawn, "label": look.label, "popups": True, "places": True, **_ramp(features, look)}
    named = ", ".join(labels[:_NAMED]) + (", and more" if len(labels) > _NAMED else "")
    count = f"{len(features):,} feature{'' if len(features) == 1 else 's'}"
    parts = [
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n',
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n',
        f"<title>{html.escape(title)}</title>\n<style>\n{style.CSS}</style>\n",
        f'<script src="{maps.PATH}map.js"></script>\n</head>\n<body class="louvre">\n<main>\n',
        f'<p class="l-kicker">Map &middot; {count}</p>\n<h1>{html.escape(title)}</h1>\n',
        f'<p class="l-lede">{html.escape(look.description)}</p>\n' if look.description else "",
        '<figure class="l-plot">\n',
        f'<div class="l-map" id="map" role="img" aria-label="A map of {count}: {html.escape(named)}"></div>\n',
        _key(features, look),
        f'<p class="l-source">{_CREDIT}</p>\n</figure>\n',
        '<h2>Each feature</h2>\n<ol class="l-features">\n',
        *(_row(feature, label, look, i) for i, (feature, label) in enumerate(zip(features, labels, strict=True))),
        "</ol>\n</main>\n",
        f'<script>\nLouvreMap.draw("map", {_script_json(options)});\n</script>\n</body>\n</html>\n',
    ]
    return "".join(parts)


class PlaceKind(StrEnum):
    """What a thread on a map is on."""

    #: One of the data's features, found again by its id.
    FEATURE = "feature"
    #: A point on the earth, which stays where it is.
    POINT = "point"
    #: A box drawn on the map, its sides along meridians and parallels, which stays where it is as a point does.
    BOX = "box"


@dataclass(frozen=True)
class Place:
    """Where on a map a thread is: a feature of the data, or a point or a box on the earth, as words are a passage's.

    A feature is named by its layer and its id, its label and geometry kept beside them as they were when the thread
    was opened; a point by its coordinates, and a box by its corners. Words, never positions (REQUIREMENTS L2): a
    pixel is never kept.
    """

    kind: PlaceKind
    #: The feature's layer: `data`, the one layer a GeoJSON version has. Empty for a point.
    layer: str = ""
    #: The feature's id: its GeoJSON `id`, or without one its label. Empty for a point.
    id: str = ""
    #: The feature's label, when the thread was opened.
    label: str = ""
    #: The feature's geometry, when the thread was opened, or the point's or the box's, as GeoJSON: a box's is a
    #: Polygon with its `bbox`, west, south, east, and north.
    geometry: Mapping[str, object] | None = None
    #: How near a point read from where a reader stood is sure to be, in whole metres; None for any other place.
    accuracy: int | None = None

    def quote(self) -> str:
        """Say where the thread is in words, for a reader that knows only words, as its anchor's `exact`.

        Returns:
            The feature's label, the point's latitude and longitude, and how sure a reading of it is, or the box's
            south-west and north-east corners'.
        """
        match self.kind:
            case PlaceKind.FEATURE:
                return self.label
            case PlaceKind.POINT:
                within = "" if self.accuracy is None else f", within {self.accuracy:,} m"
                return _said(*_point(self.geometry)) + within
            case PlaceKind.BOX:
                west, south, east, north = _box(self.geometry)
                return f"{_said(west, south)} to {_said(east, north)}"
            case _:
                assert_never(self.kind)

    def json(self) -> dict[str, object]:
        """Give the place as the API and the tools show it, and as it is stored.

        Returns:
            Its kind, and its layer, id, label, and geometry for a feature, or its geometry for a point or a box.
        """
        if self.kind == PlaceKind.POINT and self.accuracy is not None:
            return {"kind": self.kind, "geometry": dict(self.geometry or {}), "accuracy": self.accuracy}
        if self.kind in {PlaceKind.POINT, PlaceKind.BOX}:
            return {"kind": self.kind, "geometry": dict(self.geometry or {})}
        return {"kind": self.kind, "layer": self.layer, "id": self.id, "label": self.label, "geometry": self.geometry}


#: The one layer a GeoJSON version has, as a feature's place names it.
LAYER = "data"
#: The property the page gives each feature for the kit: its id, as a place names it.
PLACE_ID = "louvre:id"


@dataclass(frozen=True)
class Pick:
    """What a reader picked on a map, as their page says it: a feature by its id, or a point or a box on the earth."""

    kind: PlaceKind
    #: The feature's id, as the page's map names it.
    id: str = ""
    #: The point's longitude and latitude, or the box's west, south, east, and north.
    coordinates: Sequence[float] = ()
    #: For a point read from where the reader stands, how near the reading is sure to be, in metres; None otherwise.
    accuracy: float | None = None


def place_on(content: str, pick: Pick) -> Place:
    """Make the place a reader picked on a GeoJSON version's map, from what the version itself says of it.

    Only the feature's id, or the point's or the box's coordinates and a point's accuracy, are taken from the reader
    (D008): the label and geometry are the version's own.

    Returns:
        The place.

    Raises:
        GeodataError: The content is not GeoJSON Louvre draws, the point or the box is off the earth, the box has no
            area or its west is east of its east, no feature has the id, or an accuracy is given for what is not a
            point or is not a number of metres from 0 to `MAX_ACCURACY`.
    """
    features, look = check(content)
    if pick.accuracy is not None and pick.kind != PlaceKind.POINT:
        raise GeodataError("only a point, read from where a reader stands, has an accuracy")
    match pick.kind:
        case PlaceKind.POINT:
            _position(list(pick.coordinates), "the point")
            point = [float(c) for c in pick.coordinates[:2]]
            accuracy = None if pick.accuracy is None else _accuracy(pick.accuracy)
            return Place(pick.kind, geometry={"type": "Point", "coordinates": point}, accuracy=accuracy)
        case PlaceKind.BOX:
            return Place(pick.kind, geometry=_box_geometry(pick.coordinates))
        case PlaceKind.FEATURE:
            for i, feature in enumerate(features):
                if pick.id and _id_of(feature, look) == pick.id:
                    geometry = feature.get("geometry")
                    shape = geometry if isinstance(geometry, dict) else None
                    return Place(pick.kind, LAYER, pick.id, _label(feature, look, i), shape)
            raise GeodataError(f"no feature of the data has the id {pick.id!r}")
        case _:
            assert_never(pick.kind)


def found(content: str, place: Place) -> bool:
    """Tell whether a place is on a version's map: its feature, by its layer and id, or any point or box.

    A feature found nowhere is gone, and never moves to the nearest one.

    Returns:
        Whether it is there.
    """
    try:
        features, look = check(content)
    except GeodataError:
        return False
    if place.kind in {PlaceKind.POINT, PlaceKind.BOX}:
        return True
    return place.layer == LAYER and any(_id_of(feature, look) == place.id for feature in features)


def place_from(stored: Mapping[str, object]) -> Place:
    """Read a place as it is stored.

    Returns:
        The place.
    """
    geometry = stored.get("geometry")
    accuracy = stored.get("accuracy")
    return Place(
        PlaceKind(str(stored["kind"])),
        str(stored.get("layer", "")),
        str(stored.get("id", "")),
        str(stored.get("label", "")),
        geometry if isinstance(geometry, dict) else None,
        accuracy if isinstance(accuracy, int) and not isinstance(accuracy, bool) else None,
    )


class Difference(StrEnum):
    """What a later version of a map did to one of the earlier version's features, found by its id as a place is."""

    #: A feature the earlier version did not have.
    ADDED = "added"
    #: A feature the later version does not have.
    REMOVED = "removed"
    #: A feature both have, its geometry not the same: moved, or reshaped where it was.
    MOVED = "moved"


@dataclass(frozen=True)
class FeatureChange:
    """One feature a later version of a map added, removed, or moved (REQUIREMENTS U8, U10)."""

    kind: Difference
    #: The feature's id, as a place on the map names it.
    id: str
    #: Its label: in the later version, or for one removed, in the earlier.
    label: str
    #: Its geometry in the later version, or for one removed, in the earlier.
    geometry: Mapping[str, object] | None
    #: For one moved, its geometry in the earlier version; None otherwise.
    was: Mapping[str, object] | None = None
    #: For one moved, how far its middle moved, in whole metres: 0 for one reshaped where it was.
    metres: int = 0
    #: Which way its middle moved, such as "north-east"; empty when it did not.
    toward: str = ""

    def json(self) -> dict[str, object]:
        """Give the change as the API shows it.

        Returns:
            Its kind, the feature's id and label, its geometry, and for one moved its earlier geometry and how far
            and which way it moved.
        """
        return {
            "kind": self.kind,
            "id": self.id,
            "label": self.label,
            "geometry": self.geometry,
            "was": self.was,
            "metres": self.metres,
            "toward": self.toward,
        }


def differences(old: str, new: str) -> list[FeatureChange]:
    """Find the features a later version of a map, `new`, added, removed, or moved from an earlier one's, `old`.

    A feature is found in each by its id, as a place is: its GeoJSON `id`, or without one its label. One with neither,
    which no place names either, is left out, and so is a second feature with an id the first already has. Changes to
    a feature's properties alone are its words', which the versions' texts compare (louvre.core.compare).

    Returns:
        Each feature added or moved, in the later version's order, then each removed, in the earlier version's.
    """
    try:
        earlier, later = _by_id(old), _by_id(new)
    except GeodataError:
        return []
    found: list[FeatureChange] = []
    for key, (label, geometry) in later.items():
        if key not in earlier:
            found.append(FeatureChange(Difference.ADDED, key, label, geometry))
            continue
        was = earlier[key][1]
        if was != geometry:
            metres, toward = _moved(was, geometry)
            found.append(FeatureChange(Difference.MOVED, key, label, geometry, was, metres, toward))
    found += [
        FeatureChange(Difference.REMOVED, key, label, geometry)
        for key, (label, geometry) in earlier.items()
        if key not in later
    ]
    return found


def near(place: Place, changes: Iterable[FeatureChange]) -> bool:
    """Say whether a place is in or beside what a later version of its map changed.

    A feature is when it moved; a point or a box when a feature added, removed, or moved is in it, or over it, as
    their boxes say.

    Returns:
        Whether it is.
    """
    match place.kind:
        case PlaceKind.FEATURE:
            return any(c.kind == Difference.MOVED and c.id == place.id for c in changes)
        case PlaceKind.POINT:
            lon, lat = _point(place.geometry)
            area = (lon, lat, lon, lat)
        case PlaceKind.BOX:
            area = _box(place.geometry)
        case _:
            assert_never(place.kind)
    return any(_overlap(area, _bounds(shape)) for c in changes for shape in (c.geometry, c.was))


def _accuracy(given: float) -> int:
    """Read a point's accuracy, in metres, as a reader's device gave it.

    Returns:
        It, in whole metres, rounded up: a reading is never surer than it says.

    Raises:
        GeodataError: It is not a number of metres from 0 to `MAX_ACCURACY`.
    """
    if not (_is_number(given) and math.isfinite(given) and 0 < given <= MAX_ACCURACY):
        raise GeodataError(f"a point's accuracy is a number of metres, over 0 and at most {MAX_ACCURACY:,}")
    return max(_LEAST_ACCURACY, math.ceil(given))


def _by_id(content: str) -> dict[str, tuple[str, Mapping[str, object] | None]]:
    """Read a version's features by their ids, as places name them, each with its label and geometry.

    Returns:
        Each feature that has an id, the first of any that share one, in the version's order.

    Raises:
        GeodataError: The content is not GeoJSON Louvre draws.
    """
    features, look = check(content)
    found: dict[str, tuple[str, Mapping[str, object] | None]] = {}
    for i, feature in enumerate(features):
        key = _id_of(feature, look)
        geometry = feature.get("geometry")
        if key and key not in found:
            found[key] = (_label(feature, look, i), geometry if isinstance(geometry, dict) else None)
    return found


def _moved(was: Mapping[str, object] | None, now: Mapping[str, object] | None) -> tuple[int, str]:
    """Measure how far, and which way, a geometry's middle moved: its box's middle, as near as a change says it.

    Returns:
        The metres, along the earth, and the way, one of `_TOWARD`; 0 and empty when it moved under a metre, or
        either has no geometry.
    """
    before, after = _bounds(was), _bounds(now)
    if before is None or after is None:
        return 0, ""
    lon1, lat1 = (before[0] + before[2]) / 2, (before[1] + before[3]) / 2
    lon2, lat2 = (after[0] + after[2]) / 2, (after[1] + after[3]) / 2
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = phi2 - phi1, math.radians(lon2 - lon1)
    # The haversine: the great circle's length between the two middles.
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    metres = round(2 * _EARTH * math.asin(min(1.0, math.sqrt(h))))
    if metres < 1:
        return 0, ""
    bearing = math.atan2(
        math.sin(dlambda) * math.cos(phi2),
        math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda),
    )
    return metres, _TOWARD[round(math.degrees(bearing) % 360 / 45) % len(_TOWARD)]


def _bounds(geometry: Mapping[str, object] | None) -> tuple[float, float, float, float] | None:
    """Find the box around a checked geometry's positions.

    Returns:
        Its west, south, east, and north, or None for no geometry, or one with no positions.
    """
    positions = list(_every_position(geometry))
    if not positions:
        return None
    lons, lats = [p[0] for p in positions], [p[1] for p in positions]
    return min(lons), min(lats), max(lons), max(lats)


def _every_position(geometry: object) -> Iterator[tuple[float, float]]:
    """Read every position of a checked geometry, a collection's parts' too.

    Yields:
        Each position's longitude and latitude.
    """
    if not isinstance(geometry, dict):
        return
    if geometry.get("type") == "GeometryCollection":
        for part in geometry.get("geometries") or []:
            yield from _every_position(part)
        return
    stack: list[object] = [geometry.get("coordinates")]
    while stack:
        value = stack.pop()
        if isinstance(value, list) and value and all(map(_is_number, value)):
            yield float(value[0]), float(value[1])
        elif isinstance(value, list):
            stack.extend(value)


def _overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float] | None) -> bool:
    return b is not None and a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def _feature(feature: object, where: str) -> Mapping[str, object]:
    if not isinstance(feature, dict) or feature.get("type") != "Feature":
        raise GeodataError(f"{where} is not a Feature")
    properties = feature.get("properties")
    if properties is not None and not isinstance(properties, dict):
        raise GeodataError(f"{where}.properties is not an object")
    geometry = feature.get("geometry")
    if geometry is not None:
        _geometry(geometry, f"{where}.geometry")
    return feature


def _geometry(geometry: object, where: str) -> None:
    if not isinstance(geometry, dict):
        raise GeodataError(f"{where} is not a geometry")
    kind = geometry.get("type")
    if kind == "GeometryCollection":
        parts = geometry.get("geometries")
        if not isinstance(parts, list):
            raise GeodataError(f"{where}.geometries is not a list")
        for i, part in enumerate(parts):
            _geometry(part, f"{where}.geometries[{i}]")
        return
    if not isinstance(kind, str) or kind not in _DEPTH:
        raise GeodataError(f"{where} has no geometry type RFC 7946 has")
    _positions(geometry.get("coordinates"), _DEPTH[kind], kind, f"{where}.coordinates")


def _positions(value: object, depth: int, kind: str, where: str) -> None:
    if depth == 0:
        _position(value, where)
        return
    if not isinstance(value, list):
        raise GeodataError(f"{where} is not a list")
    least = {("LineString", 1): 2, ("MultiLineString", 1): 2, ("Polygon", 1): 4, ("MultiPolygon", 1): 4}
    if len(value) < least.get((kind, depth), 0):
        raise GeodataError(f"{where} has too few positions for a {kind}")
    if kind in {"Polygon", "MultiPolygon"} and depth == 1 and value and value[0] != value[-1]:
        raise GeodataError(f"{where} is a ring that does not close: its last position is not its first")
    for i, item in enumerate(value):
        _positions(item, depth - 1, kind, f"{where}[{i}]")


def _position(value: object, where: str) -> None:
    if not isinstance(value, list) or len(value) not in _POSITION or not all(map(_is_number, value)):
        raise GeodataError(f"{where} is not a position: [longitude, latitude]")
    lon, lat = float(value[0]), float(value[1])
    if not (math.isfinite(lon) and math.isfinite(lat) and abs(lon) <= _LONGITUDE and abs(lat) <= _LATITUDE):
        raise GeodataError(f"{where} is off the earth: longitude first, then latitude, in degrees")


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _where(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"]) or "its top"


def _label(feature: Mapping[str, object], look: Look, i: int) -> str:
    found = _properties(feature).get(look.label)
    return _shown(found) if found is not None and _shown(found) else f"Feature {i + 1}"


def _properties(feature: Mapping[str, object]) -> Mapping[str, object]:
    """Read a checked feature's properties.

    Returns:
        Its properties, none when it has null.
    """
    found = feature.get("properties")
    return found if isinstance(found, dict) else {}


def _shown(value: object) -> str:
    """Write a property's value as a reader reads it.

    Returns:
        The value: yes or no for a boolean, a number or a string as it is, and anything else as JSON.
    """
    match value:
        case bool():
            return "yes" if value else "no"
        case int() | float() | str():
            return str(value)
        case _:
            return json.dumps(value, ensure_ascii=False)


def _drawn(features: Sequence[Mapping[str, object]], look: Look) -> Iterator[Mapping[str, object]]:
    """Give each feature to the kit as the look declares it: in focus or not.

    Yields:
        Each feature, its `focus` set when the look names what the map is about.
    """
    for feature in features:
        properties = dict(_properties(feature))
        if look.focus is not None:
            properties["focus"] = properties.get(look.focus.property) in look.focus.equals
        # The id a place on it is named by, as the server names it, so the kit and Louvre never read it apart.
        properties[PLACE_ID] = _id_of(feature, look)
        yield {"type": "Feature", "properties": properties, "geometry": feature.get("geometry")}


def _ramp(features: Sequence[Mapping[str, object]], look: Look) -> dict[str, object]:
    values = list(_ramped(features, look))
    if look.ramp is None or not values:
        return {}
    return {"ramp": {"property": look.ramp.property, "min": min(values), "max": max(values)}}


def _ramped(features: Sequence[Mapping[str, object]], look: Look) -> Iterator[float]:
    """Read the ramp's property of each feature that has it as a number.

    Yields:
        Each value.
    """
    if look.ramp is None:
        return
    for feature in features:
        value = _properties(feature).get(look.ramp.property)
        if isinstance(value, int | float) and _is_number(value) and math.isfinite(value):
            yield float(value)


def _key(features: Sequence[Mapping[str, object]], look: Look) -> str:
    spans = []
    if look.key is not None:
        spans.append(f'<span class="l-focus">{html.escape(look.key.focus)}</span>')
        if look.key.rest:
            spans.append(f"<span>{html.escape(look.key.rest)}</span>")
    values = list(_ramped(features, look))
    if look.ramp is not None and values:
        unit = f"&nbsp;{html.escape(look.ramp.unit)}" if look.ramp.unit else ""
        low, high = _number(min(values)), _number(max(values))
        spans.append(
            f'<span class="l-ramp">{html.escape(look.ramp.property)}: {low}{unit}'
            f'<i aria-hidden="true"></i>{high}{unit}</span>',
        )
    return f'<p class="l-key">{"".join(spans)}</p>\n' if spans else ""


def _number(value: float) -> str:
    return f"{value:,.6g}"


def _row(feature: Mapping[str, object], label: str, look: Look, i: int) -> str:
    properties = _properties(feature)
    hidden = {*_KIT_PROPERTIES, look.label}
    shown = [(k, v) for k, v in properties.items() if k not in hidden and v is not None]
    # Each name and its value in a `div`, as HTML lets a `dl` group them, so the two wrap as one.
    facts = "".join(f"<div><dt>{html.escape(str(k))}</dt><dd>{html.escape(_shown(v))}</dd></div>" for k, v in shown)
    return f'<li id="f-{i + 1}"><b>{html.escape(label)}</b>' + (f"<dl>{facts}</dl>" if facts else "") + "</li>\n"


def _script_json(value: object) -> str:
    """Write `value` as JSON that is safe inside a `<script>` element: no `<`, `>`, or `&` to end it early.

    Returns:
        The JSON.
    """
    written = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return written.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _id_of(feature: Mapping[str, object], look: Look) -> str:
    """Name a feature as a place does: its GeoJSON `id`, or without one its label property.

    Returns:
        The id, or empty when it has neither.
    """
    given = feature.get("id")
    if isinstance(given, str | int | float) and not isinstance(given, bool):
        return str(given)
    label = _properties(feature).get(look.label)
    return _shown(label) if label is not None else ""


def _point(geometry: Mapping[str, object] | None) -> tuple[float, float]:
    coordinates = (geometry or {}).get("coordinates")
    if isinstance(coordinates, list) and len(coordinates) >= 2:  # noqa: PLR2004  (longitude and latitude)
        return float(coordinates[0]), float(coordinates[1])
    return 0.0, 0.0


def _said(lon: float, lat: float) -> str:
    """Say a point as Louvre quotes one, and as the kit does: its latitude, then its longitude, to five places.

    Returns:
        The point in words.
    """
    return f"{abs(lat):.5f}° {'N' if lat >= 0 else 'S'}, {abs(lon):.5f}° {'E' if lon >= 0 else 'W'}"


def _box_geometry(coordinates: Sequence[float]) -> dict[str, object]:
    """Make a box's geometry from its west, south, east, and north, as a reader drew it.

    Returns:
        A Polygon, its ring from the south-west corner anticlockwise, with its `bbox`.

    Raises:
        GeodataError: It is not four numbers, a corner is off the earth, or it has no area, or its west is east of its
            east: a map Louvre draws never crosses the antimeridian.
    """
    if len(coordinates) != _BOX or not all(map(_is_number, coordinates)):
        raise GeodataError("the box is not [west, south, east, north]")
    west, south, east, north = (float(c) for c in coordinates)
    _position([west, south], "the box's south-west corner")
    _position([east, north], "the box's north-east corner")
    if not (west < east and south < north):
        raise GeodataError("the box has no area: its west must be west of its east, and its south south of its north")
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return {"type": "Polygon", "bbox": [west, south, east, north], "coordinates": [ring]}


def _box(geometry: Mapping[str, object] | None) -> tuple[float, float, float, float]:
    bbox = (geometry or {}).get("bbox")
    if isinstance(bbox, list) and len(bbox) == _BOX:
        west, south, east, north = (float(c) for c in bbox)
        return west, south, east, north
    return 0.0, 0.0, 0.0, 0.0
