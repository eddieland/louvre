"""GeoJSON as an artifact: what Louvre accepts of it, and the page it draws it as."""

import contextlib
import json
from unittest import mock

import pytest
from hypothesis import given
from hypothesis import strategies as st
from syrupy.assertion import SnapshotAssertion

from louvre.core import geodata, render
from louvre.core.geodata import GeodataError, check, page

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
