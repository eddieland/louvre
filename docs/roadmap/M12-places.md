# M12. Comments on places

REQUIREMENTS U10, L2, L4, D008. A thread anchored on a map's feature, a point, or an area, as a passage's is on its
words.

- On a map in the kit, a tap on a feature, a point, or a box drawn on it opens a thread in the margin, as selecting
  words does.
- The anchor names a layer and a feature's id, with the feature's label and geometry kept beside it, or a point or a
  box in WGS 84. Words, never positions (L2): on a map a feature's id and a place's coordinates are its words, and a
  pixel is a position.
- On a new version a feature's thread is found again by its layer and id; found nowhere, it reads `passage_gone`, and
  never moves to the nearest feature. A point or a box stays where it is on the earth.
- The kit carries the bridge's half for maps: it reports a tap on a map as the bridge reports a selection, and Louvre
  trusts it no further (D008). Both sides find a place alike, held by fixtures as anchors are.
- A place's thread also carries a quote, its feature's label or its coordinates as text, so a reader of
  `thread_list` and `comment_feed` that knows only words reads it unchanged; whether canopy's contract takes the
  place beside the quote is settled with canopy first (REQUIREMENTS, Open).

Accept: on a phone and a laptop, the operator comments on a feature and on a point; an agent reads both threads over
MCP and publishes a version without the feature, whose thread reads `passage_gone` while the point's stays.

Status: built, for the operator to accept: features, points, and boxes. The place is Louvre's own beside the contract
(D011): a thread carries `place` beside an anchor whose words are the feature's label, the point's coordinates, or the
box's corners. A feature is named by its GeoJSON `id`, or without one by its label. A box is drawn with the map's box
button, by a drag, a finger's too, and kept as a GeoJSON Polygon with its `bbox`; it is the kit's one change in
`louvre-map-2`, which holds only its `kit.js` and serves `louvre-map-1`'s other files. People open place threads on
the web; `comment_create` stays the contract's, words only.
