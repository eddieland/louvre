# M11. Geodata as an artifact

REQUIREMENTS U9, U4, L2. An agent publishes data, and Louvre draws it as a map, as it shows Markdown in its style.

- A content type for GeoJSON (`application/geo+json`, RFC 7946: coordinates in WGS 84), drawn by Louvre with the kit
  (M10): each layer styled by a small style the artifact declares, a property and a ramp from the guide, with a
  legend, and a feature's properties shown on a tap.
- Its visible text is its features' labels and properties, in feature order, so a thread on it is anchored by words
  as on any artifact (L2), before M12 anchors one on a place.
- A limit on its size; larger data waits on files beside it (M9) in a format drawn by tiles, such as FlatGeobuf or
  PMTiles (REQUIREMENTS, Open).
- A new content type grows canopy's contract, so it is settled with canopy first (REQUIREMENTS, Open).

Accept: an agent publishes a GeoJSON layer, and the operator, on a phone and a laptop, taps a feature, reads its
properties, and comments on them; a new version keeps the thread.

Status: not started.
