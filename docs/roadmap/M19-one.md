# M19. Louvre 1.0

REQUIREMENTS U6, U9, D004, D008. Every milestone before it accepted and live (M6), and what a published page depends on
frozen at a version.

- `louvre-1` and `louvre-map-1` freeze: their files never change again, their hashes pinned by the tests, and a change
  is `louvre-2` or `louvre-map-2` beside them, every version served (D008). `style_get` hands the newest and names
  them all; the guide says a page names the one it was built with.
- Tag `v1.0.0` (D004): the image and the Helm chart pin it, as the chart's README asks of a production release.
- REQUIREMENTS: each "awaiting the operator's word" becomes Built, and the open list holds only what is still open;
  each milestone's `Status:` reads done, with what it taught.
- The demo's pages, published before the tag, render after a `louvre-2` ships exactly as before it.

Accept: the operator reads a page published against `louvre-1` before the tag, on a phone and a laptop, after a change
to the style has shipped as `louvre-2`, and it has not changed; the deployment runs the tagged image.

Status: proposed 2026-11-07, for the operator to order or strike; not started. Not before M6 and the operator's
acceptance of M2, M3, and M7 to M13, which are built and waiting.
