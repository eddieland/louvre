# M17. Larger maps

REQUIREMENTS U9, U10, L8, D008, Open. Geodata past what M11 holds in a version, and street tiles that do not depend on
OpenFreeMap's moment.

- Data past M11's limit (2,000 features, 2 MB) is published as a file beside a version (L8) in a format the kit draws
  by tiles without reading it whole: PMTiles, one file read by ranges, which `/content/.../<key>/` answers; a limit of
  its own on such a file, refused with a code when passed. Rejected: FlatGeobuf (the page decodes features itself,
  and a phone pays for it).
- Files are not text (M9), so a thread on tiled data is on a place: a point or a box, or a feature by the id and
  label the kit reports from the tile, which Louvre keeps with the thread and finds again by id in a later version's
  file; found nowhere it reads `passage_gone` (L2, M12).
- The street tiles Louvre passes on (D008) are cached, so a tile is fetched from OpenFreeMap once and a reader never
  waits on it twice; a deployment that would rather host its own names them (`LOUVRE_STREETS`), as PMTiles too.
- The guide and `style_check` say when a map's data belongs in a tiled file rather than inline, and the demo
  publishes one such map.

Accept: an agent publishes a layer of a hundred thousand features as a file beside a page; the operator pans it on a
phone and a laptop, taps a feature, and comments on it, and a new version keeps the thread; a city's street tiles,
read by two people, leave Louvre for OpenFreeMap once.

Status: proposed 2026-11-07, for the operator to order or strike; not started. Raised on the concrete reason M11
names: a version holds 2,000 features, and a trace or an asset register holds more.
