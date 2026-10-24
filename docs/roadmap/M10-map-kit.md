# M10. A map kit, served by Louvre

REQUIREMENTS U9, U6, U4, L7. An artifact draws a map with a basemap, from a kit Louvre serves at a version, and still
loads nothing from the network.

- `louvre-map-1`: a pinned map library (MapLibre GL JS) and a basemap (Protomaps, as PMTiles), drawn dark and light
  from Louvre's tokens, served by Louvre at the kit's versioned path. The artifact policy allows that path and nothing
  else beyond the page's own files (M9). An artifact names the kit's version, so a later kit never redraws a published
  map, as with the style.
- The kit's routes read no session and answer every caller alike: a sandboxed frame's requests carry no origin, and
  must not need one.
- Over MCP as the style is (U6): a starter map page, and the guide's map components, a legend, a scale bar, and the
  basemap's attribution, which its data's license requires.
- `style_check` errors on a map that names no kit version or drops the attribution, and warns on one with no legend,
  or with more data inline than a phone draws well.
- On a phone, a page draws one map: a phone allows few WebGL contexts at once, and a board's frames (U5) count
  against them.
- The demo publishes a map report.

Accept: an agent publishes a map in the kit, and the operator reads it on a phone and a laptop, panning and zooming
it, with no request leaving Louvre; the screen matrix holds the demo's map at every size.

Status: built, for the operator to accept. The basemap is Natural Earth's 1:50m as GeoJSON (land, lakes, borders,
and cities, built by `scripts/basemap.py`), not Protomaps' PMTiles: Protomaps' builds were out of the build machine's
reach, and Natural Earth is public domain, so the credit is a courtesy the check still asks for. A street's detail is
for a later kit (REQUIREMENTS, Open). A phone keeps one map drawn at a time, the one in view.
