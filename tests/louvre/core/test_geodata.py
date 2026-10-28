"""GeoJSON as an artifact: what Louvre accepts of it, and the page it draws it as."""

import contextlib
import json
import re
from unittest import mock

import pytest
from hypothesis import given
from hypothesis import strategies as st
from syrupy.assertion import SnapshotAssertion

from louvre.core import geodata, render
from louvre.core.geodata import GeodataError, PlaceKind, check, page

#: A point, a line, and an area, the second in focus by its status, and a ramp of one number.
POLES = {
    "type": "FeatureCollection",
    "louvre": {
        "description": "One pole of three needs a crew.",
        "focus": {"property": "status", "equals": ["lamp out"]},
        "ramp": {"property": "lux", "unit": "lx"},
        "key": {"focus": "Needs a crew", "rest": "Working"},
    },
    "features": [
        {
            "type": "Feature",
            "properties": {"name": "P-101", "lux": 12},
            "geometry": {"type": "Point", "coordinates": [-9.1, 38.7]},
        },
        {
            "type": "Feature",
            "properties": {"name": "P-102", "status": "lamp out", "lux": 0, "note": "</script><b>hi</b>"},
            "geometry": {"type": "LineString", "coordinates": [[-9.1, 38.7], [-9.2, 38.8]]},
        },
        {
            "type": "Feature",
            "properties": {"lux": 30.5, "parts": [1, 2], "lit": True},
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        },
    ],
}

#: Any JSON value, nested a few deep.
JSON = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False) | st.text(max_size=8),
    lambda inner: st.lists(inner, max_size=4) | st.dictionaries(st.text(max_size=8), inner, max_size=4),
    max_leaves=20,
)


def test_a_feature_collection_or_a_feature_is_read_with_how_it_is_drawn() -> None:
    features, look = check(json.dumps(POLES))
    [one], plain = check(json.dumps(POLES["features"][0]))

    assert len(features) == 3
    assert look.focus is not None
    assert look.focus.equals == ("lamp out",)
    assert one["properties"] == {"name": "P-101", "lux": 12}
    assert plain.label == "name"


@pytest.mark.parametrize(
    ("data", "why"),
    [
        ("not json", "not JSON"),
        ([], "is an object"),
        ({"type": "Topology"}, "FeatureCollection, or a Feature"),
        ({"type": "FeatureCollection", "features": {}}, "are a list"),
        ({"type": "Feature", "geometry": {"type": "Circle", "coordinates": [0, 0]}}, "no geometry type"),
        ({"type": "Feature", "geometry": {"type": "Point", "coordinates": [0, 91]}}, "off the earth"),
        ({"type": "Feature", "geometry": {"type": "Point", "coordinates": ["0", "1"]}}, "not a position"),
        ({"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[0, 0]]}}, "too few positions"),
        (
            {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]}},
            "close",
        ),
        ({"type": "Feature", "properties": [], "geometry": None}, "properties is not an object"),
        ({"type": "Feature", "geometry": None, "louvre": {"ramp": {"unit": "ms"}}}, "louvre member"),
        ({"type": "Feature", "geometry": None, "louvre": {"colour": "red"}}, "louvre member"),
    ],
)
def test_what_is_not_geojson_louvre_draws_is_refused_saying_why(data: object, why: str) -> None:
    with pytest.raises(GeodataError, match=why):
        check(data if isinstance(data, str) else json.dumps(data))


def test_no_more_than_the_most_features_a_page_lists() -> None:
    with mock.patch.object(geodata, "MAX_FEATURES", 2), pytest.raises(GeodataError, match="3 features, over 2"):
        check(json.dumps(POLES))


@given(JSON)
def test_any_json_is_read_or_refused_and_nothing_else(data: object) -> None:
    for content in (json.dumps(data), json.dumps({"type": "FeatureCollection", "features": [data]})):
        with contextlib.suppress(GeodataError):
            check(content)


def test_its_page_is_its_map_its_key_and_each_feature_under_it(snapshot: SnapshotAssertion) -> None:
    drawn = page(json.dumps(POLES), "One pole needs a crew")

    assert drawn == snapshot
    # A property's words cannot end the script that draws the map, or the page's markup.
    assert drawn.count("</script>") == 2
    assert "<b>hi</b>" not in drawn


def test_its_text_is_its_features_labels_and_properties_in_order() -> None:
    text = render.text_of("application/geo+json", json.dumps(POLES))

    assert (
        "P-101 lux 12 P-102 status lamp out lux 0 note </script><b>hi</b> Feature 3 lux 30.5 parts [1, 2] lit yes"
        in text
    )
    assert "One pole of three needs a crew." in text


def test_a_box_drawn_on_the_map_is_kept_by_its_sides_said_by_its_corners_and_never_gone() -> None:
    content = json.dumps(POLES)

    box = geodata.place_on(content, geodata.Pick(geodata.PlaceKind.BOX, coordinates=(-9.2, 38.65, -9.05, 38.8)))

    assert box.json() == {
        "kind": "box",
        "geometry": {
            "type": "Polygon",
            "bbox": [-9.2, 38.65, -9.05, 38.8],
            "coordinates": [[[-9.2, 38.65], [-9.05, 38.65], [-9.05, 38.8], [-9.2, 38.8], [-9.2, 38.65]]],
        },
    }
    assert box.quote() == "38.65000° N, 9.20000° W to 38.80000° N, 9.05000° W"
    assert geodata.place_from(box.json()) == box
    assert geodata.found(json.dumps({"type": "FeatureCollection", "features": []}), box)


@pytest.mark.parametrize(
    ("coordinates", "why"),
    [
        ((-9.2, 38.65), "is not [west, south, east, north]"),
        ((-9.05, 38.65, -9.2, 38.8), "has no area"),
        ((-9.2, 38.8, -9.05, 38.8), "has no area"),
        ((-9.2, 38.65, -9.05, 91), "is off the earth"),
        ((-190, 38.65, -9.05, 38.8), "is off the earth"),
    ],
)
def test_a_box_with_no_area_or_off_the_earth_is_refused_saying_why(coordinates: tuple[float, ...], why: str) -> None:
    with pytest.raises(GeodataError, match=re.escape(why)):
        geodata.place_on(json.dumps(POLES), geodata.Pick(geodata.PlaceKind.BOX, coordinates=coordinates))


def _poles(*poles: tuple[str, list[float]], status: str = "working") -> str:
    """Write poles as GeoJSON, each a point named by its label, as the demo's are.

    Returns:
        The GeoJSON.
    """
    features = [
        {
            "type": "Feature",
            "properties": {"name": n, "status": status},
            "geometry": {"type": "Point", "coordinates": c},
        }
        for n, c in poles
    ]
    return json.dumps({"type": "FeatureCollection", "features": features})


def test_a_later_version_reads_as_the_features_it_added_removed_and_moved() -> None:
    old = _poles(("P-1", [-9.14, 38.71]), ("P-2", [-9.14, 38.72]), ("P-3", [0, 0]))
    new = _poles(("P-1", [-9.14, 38.7101]), ("P-3", [0, 0]), ("P-4", [1, 1]), status="lamp out")

    moved, added, removed = geodata.differences(old, new)

    assert (moved.kind, moved.id, moved.metres, moved.toward) == (geodata.Difference.MOVED, "P-1", 11, "north")
    assert moved.was == {"type": "Point", "coordinates": [-9.14, 38.71]}
    assert moved.geometry == {"type": "Point", "coordinates": [-9.14, 38.7101]}
    assert (added.kind, added.id, added.was) == (geodata.Difference.ADDED, "P-4", None)
    assert (removed.kind, removed.label, removed.geometry) == (
        geodata.Difference.REMOVED,
        "P-2",
        {"type": "Point", "coordinates": [-9.14, 38.72]},
    )
    # Its status changed on every pole: words, which the texts compare, and no feature's change.
    assert [c.id for c in geodata.differences(old, old.replace("working", "lamp out"))] == []


def test_a_feature_reshaped_where_it_was_moved_no_metres_and_one_with_no_id_is_left_out() -> None:
    square = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]
    larger = [[-1, -1], [2, -1], [2, 2], [-1, 2], [-1, -1]]
    area = {
        "type": "Feature",
        "properties": {"name": "Block"},
        "geometry": {"type": "Polygon", "coordinates": [square]},
    }
    nameless: dict[str, object] = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Point", "coordinates": [5, 5]},
    }
    old = json.dumps({"type": "FeatureCollection", "features": [area, nameless]})
    new = old.replace(json.dumps(square), json.dumps(larger)).replace("[5, 5]", "[6, 6]")

    [reshaped] = geodata.differences(old, new)

    assert (reshaped.id, reshaped.metres, reshaped.toward) == ("Block", 0, "")
    assert reshaped.json()["kind"] == "moved"
    assert geodata.differences("not json", new) == []


def test_a_place_is_near_a_change_when_its_feature_moved_or_a_change_is_over_it() -> None:
    old = _poles(("P-1", [-9.14, 38.71]), ("P-2", [-9.14, 38.72]))
    changes = geodata.differences(old, _poles(("P-1", [-9.15, 38.71])))
    feature = geodata.place_on(old, geodata.Pick(PlaceKind.FEATURE, "P-1"))
    still = geodata.place_on(old, geodata.Pick(PlaceKind.FEATURE, "P-2"))
    on_removed = geodata.place_on(old, geodata.Pick(PlaceKind.POINT, coordinates=(-9.14, 38.72)))
    far = geodata.place_on(old, geodata.Pick(PlaceKind.POINT, coordinates=(0, 0)))
    over = geodata.place_on(old, geodata.Pick(PlaceKind.BOX, coordinates=(-9.16, 38.70, -9.145, 38.715)))

    assert geodata.near(feature, changes)
    assert not geodata.near(still, changes)
    assert geodata.near(on_removed, changes)
    assert not geodata.near(far, changes)
    assert geodata.near(over, changes)


def test_a_point_read_where_its_reader_stood_keeps_how_sure_the_reading_is() -> None:
    content = _poles(("P-1", [-9.14, 38.71]))

    here = geodata.place_on(content, geodata.Pick(PlaceKind.POINT, coordinates=(-9.14, 38.71), accuracy=11.2))

    assert here.accuracy == 12
    assert here.quote() == "38.71000° N, 9.14000° W, within 12 m"
    assert here.json()["accuracy"] == 12
    assert geodata.place_from(here.json()) == here
    near_enough = geodata.Pick(PlaceKind.POINT, coordinates=(-9.14, 38.71), accuracy=1_500)
    assert geodata.place_on(content, near_enough).quote().endswith("within 1,500 m")


@pytest.mark.parametrize(
    "pick",
    [
        geodata.Pick(PlaceKind.POINT, coordinates=(0, 0), accuracy=0),
        geodata.Pick(PlaceKind.POINT, coordinates=(0, 0), accuracy=geodata.MAX_ACCURACY + 1),
        geodata.Pick(PlaceKind.POINT, coordinates=(0, 0), accuracy=float("nan")),
        geodata.Pick(PlaceKind.FEATURE, "P-1", accuracy=5),
    ],
)
def test_an_accuracy_is_metres_of_a_point_or_it_is_refused(pick: geodata.Pick) -> None:
    with pytest.raises(GeodataError, match="accuracy"):
        geodata.place_on(_poles(("P-1", [0, 0])), pick)
