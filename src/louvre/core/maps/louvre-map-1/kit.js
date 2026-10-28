/* louvre-map-1: draws a map in Louvre's style, with MapLibre GL JS and a basemap from Natural Earth. */
/* LouvreMap.draw(element or its id, {data, context, label, maxZoom}) draws `data`, GeoJSON or a file beside the */
/* page, on the basemap: a feature whose `focus` is true in the accent and the rest muted, or every one in the */
/* accent when none is; each labeled once with the property `label` names, "name" unless said, and numbered with */
/* its `mark` if it has one. `context`, GeoJSON or a file too, such as streets or kerbs, is drawn quietly under it. */
/* The basemap is a city's scale at most: zoomed in past it, it fades to plain ground, and the context places the */
/* data. A map is drawn while it is in view, and put away out of view when another needs its WebGL context. */
/* On a map that takes places, as one Louvre draws from GeoJSON does, a reader comments on a feature or a point by */
/* tapping it, or on a box they draw with the box button. While versions are compared it lights the features a */
/* later version added, removed, or moved; it lights a decision's option's place while it is hovered, pans and */
/* zooms to a place when asked, and rings a point read where its reader stood with how sure the reading is. */
(() => {
    const base = new URL(".", document.currentScript.src).href;
    const css = /* maplibre-gl.css */ "";
    const font = ["Noto Sans Regular"];
    const italic = ["Noto Sans Italic"];
    /** The property the kit gives each place east of the map's middle, whose label goes west of it first. */
    const EAST = "louvre:east";
    /** The property holding the label the kit gives each feature's anchor. */
    const LABEL = "louvre:label";
    /** The property holding each feature's id as a place on a map names it, which Louvre gives the GeoJSON it draws. */
    const PLACE_ID = "louvre:id";
    /** The property holding each feature's place in the data, from 1, as its row under a map Louvre draws is named. */
    const INDEX = "louvre:index";
    /** How near a tap must be to a feature to pick it, in CSS pixels: a fingertip's reach. */
    const REACH = 12;
    /** The zoom past which the basemap has faded to plain ground: about a city's, Natural Earth's finest. */
    const DETAIL = 11;
    /** How narrow a map is, in CSS pixels, for its credits to fold away: a phone's. */
    const NARROW = 480;
    /** How far in a map zooms to fit its data, unless the page says: a few streets. */
    const MAX_ZOOM = 17;
    /** A label's sides under its place and over it, as MapLibre's anchors and offsets, in ems. */
    const UNDER_OVER = ["top", [0, 0.75], "bottom", [0, -0.75]];
    /** How far in a map zooms to show a place it is asked to, unless it is in further already: a street's width. */
    const SHOW_ZOOM = 16;
    /** The longest a map flies to show a place, in ms: further, it jumps there. */
    const FLIGHT = 1500;
    /** The earth's mean radius, in metres, as a reading's accuracy is drawn around its point. */
    const EARTH = 6371008.8;
    /** The layers a feature a later version changed is lit in, which a tap on it picks. */
    const CHANGED = [
        "change-now-points",
        "change-now-lines",
        "change-now-areas",
        "change-was-points",
        "change-was-lines",
    ];

    const style = document.createElement("style");
    style.textContent = `${css}
.maplibregl-map { font: 12px var(--l-sans, system-ui, sans-serif); }
.maplibregl-ctrl-group { background: var(--l-card, #fff); box-shadow: 0 0 0 1px var(--l-rule, #ddd); }
.maplibregl-ctrl-group button + button { border-top-color: var(--l-rule, #ddd); }
.maplibregl-ctrl-group button .maplibregl-ctrl-icon { filter: var(--l-icon, none); }
.maplibregl-ctrl-attrib, .maplibregl-ctrl-attrib.maplibregl-compact {
    background: var(--l-card, #fff);
    color: var(--l-muted, #666);
}
.maplibregl-ctrl-attrib a { color: var(--l-muted, #666); }
.maplibregl-ctrl-scale {
    border-color: var(--l-muted, #666);
    background: transparent;
    color: var(--l-muted, #666);
    font: 10px var(--l-sans, system-ui, sans-serif);
}
.maplibregl-cooperative-gesture-screen {
    background: rgba(0, 0, 0, 0.55);
    font: 14px var(--l-sans, system-ui, sans-serif);
}
.maplibregl-popup-content {
    max-width: 15rem;
    padding: 0.6rem 0.75rem;
    border-radius: 4px;
    background: var(--l-card, #fff);
    box-shadow: 0 0 0 1px var(--l-rule, #ddd);
    color: var(--l-ink, #222);
    font: 12px/1.4 var(--l-sans, system-ui, sans-serif);
    user-select: none;
}
.maplibregl-popup-tip { display: none; }
.maplibregl-popup-close-button { color: var(--l-muted, #666); font-size: 16px; }
.louvre-popup b { display: block; margin: 0 1rem 0.3rem 0; font-size: 13px; }
.louvre-popup [data-text]::before { content: attr(data-text); }
.louvre-popup a { color: inherit; }
.louvre-popup dl { display: grid; grid-template-columns: auto 1fr; gap: 0.1rem 0.6rem; margin: 0; }
.louvre-popup dt { color: var(--l-muted, #666); }
.louvre-popup dd { margin: 0; overflow-wrap: anywhere; }
.maplibregl-ctrl-group button.louvre-box::before {
    content: "";
    display: block;
    width: 11px;
    height: 11px;
    margin: auto;
    border: 1.5px dashed var(--l-ink, #222);
}
.maplibregl-ctrl-group button.louvre-box[aria-pressed="true"] { background: var(--l-accent, #8a2f2a); }
.maplibregl-ctrl-group button.louvre-box[aria-pressed="true"]::before { border: 1.5px solid var(--l-card, #fff); }
/* While a box is drawn, a finger's drag is the box's, not the page's: over MapLibre's own rules, which give a */
/* one-finger drag to the page when the map does not pan. */
.louvre-boxing, .louvre-boxing .maplibregl-canvas { cursor: crosshair; touch-action: none !important; }
@media (prefers-color-scheme: dark) { :root { --l-icon: invert(0.85); } }`;
    document.head.append(style);

    /** Reads the page's colors, Louvre's tokens when it is in the house style. */
    const tokens = () => {
        const read = getComputedStyle(document.documentElement);
        const dark = matchMedia("(prefers-color-scheme: dark)").matches;
        const token = (name, light, night) => read.getPropertyValue(name).trim() || (dark ? night : light);
        return {
            bg: token("--l-bg", "#fffdf8", "#1c1915"),
            card: token("--l-card", "#f6f1e7", "#23201b"),
            ink: token("--l-ink", "#1f1b16", "#ece5d8"),
            muted: token("--l-muted", "#6d6458", "#a69c8c"),
            rule: token("--l-rule", "#e0d6c4", "#322c24"),
            accent: token("--l-accent", "#8a2f2a", "#d9776c"),
        };
    };

    /** Mixes two colors written as #rrggbb, `t` of the way from `a` to `b`; `a` when either is written otherwise. */
    const mix = (a, b, t) => {
        const rgb = (c) => (/^#[0-9a-f]{6}$/i.test(c) ? [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16)) : null);
        const [from, to] = [rgb(a), rgb(b)];
        if (!from || !to) return a;
        return `#${from.map((v, i) => Math.round(v + (to[i] - v) * t).toString(16).padStart(2, "0")).join("")}`;
    };

    /** The basemap's places: the larger ones zoomed out, and more of them zoomed in, behind the page's own. */
    const places = (id, ranks, minzoom, c) => ({
        id,
        type: "symbol",
        source: "places",
        minzoom,
        maxzoom: DETAIL,
        filter: ["all", [">=", ["get", "scalerank"], ranks[0]], ["<=", ["get", "scalerank"], ranks[1]]],
        layout: {
            "text-field": ["get", "name"],
            "text-font": italic,
            "text-size": 10.5,
            "symbol-sort-key": ["get", "scalerank"],
        },
        paint: { "text-color": mix(c.muted, c.card, 0.3), "text-halo-color": c.card, "text-halo-width": 1 },
    });

    /** OpenStreetMap's water, buildings, roads, and rail, from Louvre's street tiles, as Natural Earth's fade. */
    const streets = (c, ground, fade) => {
        const road = mix(c.rule, c.muted, 0.12);
        const major = ["motorway", "trunk", "primary"];
        const middle = ["secondary", "tertiary"];
        const width = (narrow, wide) => [
            "interpolate",
            ["exponential", 1.6],
            ["zoom"],
            DETAIL - 1,
            ["match", ["get", "class"], major, narrow[0], middle, narrow[1], narrow[2]],
            17,
            ["match", ["get", "class"], major, wide[0], middle, wide[1], wide[2]],
        ];
        const layer = (id, type, from, rest) => ({ id, type, source: "streets", "source-layer": from, ...rest });
        return [
            layer("street-water", "fill", "water", { paint: { "fill-color": c.bg, "fill-opacity": fade(0, 1) } }),
            layer("street-buildings", "fill", "building", {
                minzoom: 14,
                paint: { "fill-color": mix(ground, c.rule, 0.6) },
            }),
            layer("street-roads", "line", "transportation", {
                filter: ["!", ["in", ["get", "class"], ["literal", ["rail", "transit", "ferry", "path", "track"]]]],
                layout: { "line-cap": "round", "line-join": "round" },
                paint: {
                    "line-color": road,
                    "line-width": width([1, 0.6, 0.3], [9, 7, 4]),
                    "line-opacity": fade(0, 1),
                },
            }),
            layer("street-paths", "line", "transportation", {
                minzoom: 14,
                filter: ["in", ["get", "class"], ["literal", ["path", "track"]]],
                paint: { "line-color": road, "line-width": 1, "line-dasharray": [2, 2] },
            }),
            layer("street-rail", "line", "transportation", {
                filter: ["in", ["get", "class"], ["literal", ["rail", "transit"]]],
                paint: { "line-color": mix(c.rule, c.muted, 0.3), "line-width": 1, "line-dasharray": [3, 2] },
            }),
        ];
    };

    /** The map's style: the basemap from the kit, in the page's colors, the page's context, and its data over it. */
    const styleOf = (entry) => {
        const c = tokens();
        const { focusAll } = entry.settings;
        const focus = ["case", ["has", "focus"], ["get", "focus"], focusAll];
        const { ramp } = entry.settings;
        // A ramp colors every feature by its value, from a muted ink at its least to the accent at its most.
        const value = ramp && ["to-number", ["get", ramp.property], ramp.min];
        const ramped = ramp && ramp.max > ramp.min;
        const color = ramped
            ? ["interpolate", ["linear"], value, ramp.min, c.muted, ramp.max, c.accent]
            : ["case", focus, c.accent, c.muted];
        const ground = mix(c.card, c.rule, 0.55);
        // The hue Louvre's page marks changed words in, given by the bridge; the accent until it has been.
        const hue = changeHue || c.accent;
        const kit = (name) => ({ type: "geojson", data: `${base}basemap/${name}.json` });
        // Past a city's scale, Natural Earth's coast and borders are a kilometre or more out: they fade away, and the
        // map is plain ground, rather than put a street in the river.
        const fade = (from, to) => ["interpolate", ["linear"], ["zoom"], DETAIL - 2, from, DETAIL, to];
        return {
            version: 8,
            glyphs: `${base}glyphs/{fontstack}/{range}.pbf`,
            sources: {
                land: kit("land"),
                lakes: kit("lakes"),
                borders: kit("borders"),
                places: kit("places"),
                streets: {
                    type: "vector",
                    tiles: [`${base}streets/{z}/{x}/{y}.pbf`],
                    minzoom: DETAIL - 2,
                    maxzoom: 14,
                    attribution: "© OpenStreetMap contributors, OpenFreeMap",
                },
                context: { type: "geojson", data: entry.context },
                data: { type: "geojson", data: entry.data },
                anchors: { type: "geojson", data: entry.anchors },
                threads: { type: "geojson", data: entry.threads },
                boxes: { type: "geojson", data: entry.boxes },
                sketch: { type: "geojson", data: entry.sketch },
                reach: { type: "geojson", data: entry.reach },
                changed: { type: "geojson", data: entry.changed },
                was: { type: "geojson", data: entry.was },
                moves: { type: "geojson", data: entry.moves },
            },
            layers: [
                { id: "water", type: "background", paint: { "background-color": fade(c.bg, ground) } },
                { id: "land", type: "fill", source: "land", paint: { "fill-color": ground } },
                {
                    id: "lakes",
                    type: "fill",
                    source: "lakes",
                    paint: { "fill-color": c.bg, "fill-opacity": fade(1, 0) },
                },
                {
                    id: "borders",
                    type: "line",
                    source: "borders",
                    paint: { "line-color": mix(c.rule, c.muted, 0.3), "line-width": 0.75, "line-opacity": fade(1, 0) },
                },
                ...streets(c, ground, fade),
                places("places", [0, 2], 2.5, c),
                places("places-more", [3, 5], 5, c),
                {
                    id: "street-names",
                    type: "symbol",
                    source: "streets",
                    "source-layer": "transportation_name",
                    minzoom: 14,
                    layout: {
                        "symbol-placement": "line",
                        "text-field": ["coalesce", ["get", "name:latin"], ["get", "name"]],
                        "text-font": italic,
                        "text-size": 10.5,
                    },
                    paint: { "text-color": mix(c.muted, c.card, 0.3), "text-halo-color": ground, "text-halo-width": 1 },
                },
                {
                    id: "context-areas",
                    type: "fill",
                    source: "context",
                    filter: ["==", ["geometry-type"], "Polygon"],
                    paint: { "fill-color": mix(ground, c.rule, 0.7), "fill-outline-color": mix(c.rule, c.muted, 0.12) },
                },
                {
                    id: "context-lines",
                    type: "line",
                    source: "context",
                    filter: ["==", ["geometry-type"], "LineString"],
                    layout: { "line-cap": "round", "line-join": "round" },
                    // Quieter than any of the data: a hairline zoomed out, a street's width zoomed in.
                    paint: {
                        "line-color": mix(c.rule, c.muted, 0.12),
                        "line-width": ["interpolate", ["linear"], ["zoom"], 12, 0.5, 17, 3],
                    },
                },
                // While versions are compared, each feature the later one changed, in the change's hue: where it
                // was, dashed and hollow, for one removed or moved; a dashed line from there to where it is now, for
                // one moved; and a halo under it where it is now, for one added or moved. Stronger while it is active
                // or hovered.
                {
                    id: "change-was-areas",
                    type: "fill",
                    source: "was",
                    filter: ["==", ["geometry-type"], "Polygon"],
                    paint: { "fill-color": hue, "fill-opacity": ["case", ["get", "lit"], 0.2, 0.08] },
                },
                {
                    id: "change-was-lines",
                    type: "line",
                    source: "was",
                    filter: ["in", ["geometry-type"], ["literal", ["Polygon", "LineString"]]],
                    paint: {
                        "line-color": hue,
                        "line-width": ["case", ["get", "lit"], 2.5, 1.5],
                        "line-dasharray": [3, 2],
                    },
                },
                {
                    id: "change-was-points",
                    type: "circle",
                    source: "was",
                    filter: ["==", ["geometry-type"], "Point"],
                    paint: {
                        "circle-radius": ["case", ["get", "lit"], 7, 5],
                        "circle-color": "rgba(0, 0, 0, 0)",
                        "circle-stroke-color": hue,
                        "circle-stroke-width": 1.5,
                        "circle-stroke-opacity": ["case", ["get", "lit"], 1, 0.75],
                    },
                },
                {
                    id: "change-moves",
                    type: "line",
                    source: "moves",
                    paint: {
                        "line-color": hue,
                        "line-width": ["case", ["get", "lit"], 2, 1],
                        "line-dasharray": [1, 2],
                    },
                },
                {
                    id: "change-now-areas",
                    type: "fill",
                    source: "changed",
                    filter: ["==", ["geometry-type"], "Polygon"],
                    paint: { "fill-color": hue, "fill-opacity": ["case", ["get", "lit"], 0.45, 0.25] },
                },
                {
                    id: "change-now-lines",
                    type: "line",
                    source: "changed",
                    filter: ["in", ["geometry-type"], ["literal", ["Polygon", "LineString"]]],
                    layout: { "line-cap": "round", "line-join": "round" },
                    paint: {
                        "line-color": hue,
                        "line-width": ["case", ["get", "lit"], 9, 6],
                        "line-opacity": ["case", ["get", "lit"], 0.8, 0.5],
                    },
                },
                {
                    id: "change-now-points",
                    type: "circle",
                    source: "changed",
                    filter: ["==", ["geometry-type"], "Point"],
                    paint: {
                        "circle-radius": ["case", ["get", "lit"], 11, 9],
                        "circle-color": hue,
                        "circle-opacity": ["case", ["get", "lit"], 0.8, 0.5],
                    },
                },
                {
                    id: "areas",
                    type: "fill",
                    source: "data",
                    filter: ["==", ["geometry-type"], "Polygon"],
                    paint: { "fill-color": color, "fill-opacity": ["case", focus, 0.32, 0.18] },
                },
                {
                    id: "edges",
                    type: "line",
                    source: "data",
                    filter: ["in", ["geometry-type"], ["literal", ["Polygon", "LineString"]]],
                    layout: { "line-cap": "round", "line-join": "round" },
                    paint: {
                        "line-color": color,
                        "line-width": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            DETAIL,
                            ["case", focus, 2, 1.25],
                            DETAIL + 4,
                            ["case", focus, 3.5, 2.25],
                        ],
                    },
                },
                {
                    id: "points",
                    type: "circle",
                    source: "data",
                    filter: ["==", ["geometry-type"], "Point"],
                    paint: {
                        "circle-radius": ["case", focus, 5, 4],
                        "circle-color": ramp ? color : ["case", focus, c.accent, c.bg],
                        "circle-stroke-color": color,
                        "circle-stroke-width": 1.5,
                    },
                },
                {
                    id: "labels",
                    type: "symbol",
                    source: "anchors",
                    layout: {
                        "text-field": ["get", LABEL],
                        "text-font": font,
                        "text-size": 13,
                        // Each label takes the first side of its place with room: toward the map's middle, then
                        // under and over it, and away last, so a place at its edge is labeled inside it. The
                        // focused are placed first, and one with no room is left off: the page's table has it.
                        "text-variable-anchor-offset": [
                            "case",
                            ["get", EAST],
                            ["literal", ["right", [-0.75, 0], ...UNDER_OVER, "left", [0.75, 0]]],
                            ["literal", ["left", [0.75, 0], ...UNDER_OVER, "right", [-0.75, 0]]],
                        ],
                        "text-justify": "auto",
                        "symbol-sort-key": ["case", focus, 0, 1],
                    },
                    paint: {
                        "text-color": ["case", focus, c.ink, c.muted],
                        "text-halo-color": c.card,
                        "text-halo-width": 1.5,
                    },
                },
                {
                    id: "marks",
                    type: "symbol",
                    source: "anchors",
                    filter: ["has", "mark"],
                    layout: {
                        "text-field": ["to-string", ["get", "mark"]],
                        "text-font": font,
                        "text-size": 12,
                        "text-anchor": "bottom-right",
                        "text-offset": [-0.35, -0.35],
                        "text-allow-overlap": true,
                        "text-ignore-placement": true,
                    },
                    paint: { "text-color": c.accent, "text-halo-color": c.card, "text-halo-width": 1.5 },
                },
                // Each thread on a box, its edges in the accent, and its area tinted while it is active or hovered;
                // a draft's edges dashed, and a box being drawn, or drawn and not yet commented on, dashed too.
                {
                    id: "thread-box-areas",
                    type: "fill",
                    source: "boxes",
                    paint: { "fill-color": c.accent, "fill-opacity": ["case", ["get", "lit"], 0.12, 0] },
                },
                {
                    id: "thread-boxes",
                    type: "line",
                    source: "boxes",
                    filter: ["!=", ["get", "state"], "draft"],
                    paint: {
                        "line-color": ["case", ["==", ["get", "state"], "resolved"], c.muted, c.accent],
                        "line-width": 1.5,
                    },
                },
                {
                    id: "thread-box-drafts",
                    type: "line",
                    source: "boxes",
                    filter: ["==", ["get", "state"], "draft"],
                    paint: { "line-color": c.accent, "line-width": 1.5, "line-dasharray": [3, 2] },
                },
                {
                    id: "sketch-area",
                    type: "fill",
                    source: "sketch",
                    paint: { "fill-color": c.accent, "fill-opacity": 0.08 },
                },
                {
                    id: "sketch",
                    type: "line",
                    source: "sketch",
                    paint: { "line-color": c.accent, "line-width": 1.5, "line-dasharray": [3, 2] },
                },
                // How sure a point read where its reader stood is: a ring of that many metres around it.
                {
                    id: "reach-area",
                    type: "fill",
                    source: "reach",
                    paint: { "fill-color": c.accent, "fill-opacity": ["case", ["get", "lit"], 0.14, 0.07] },
                },
                {
                    id: "reach-line",
                    type: "line",
                    source: "reach",
                    paint: {
                        "line-color": ["case", ["==", ["get", "state"], "resolved"], c.muted, c.accent],
                        "line-width": 1,
                        "line-opacity": 0.6,
                    },
                },
                // Each thread on a place, as Louvre numbers its threads: a disc in the accent's ring, filled while
                // it is active or hovered; a draft's ring empty. A box's sits on its north-west corner. A decision's
                // option on a place is a disc too, filled, while its option is hovered or focused.
                {
                    id: "thread-marks",
                    type: "circle",
                    source: "threads",
                    paint: {
                        "circle-radius": 9,
                        "circle-color": ["case", ["get", "lit"], c.accent, c.card],
                        "circle-stroke-color": ["case", ["==", ["get", "state"], "resolved"], c.muted, c.accent],
                        "circle-stroke-width": 1.5,
                    },
                },
                {
                    id: "thread-numbers",
                    type: "symbol",
                    source: "threads",
                    layout: {
                        "text-field": ["get", "n"],
                        "text-font": font,
                        "text-size": 11,
                        "text-allow-overlap": true,
                        "text-ignore-placement": true,
                    },
                    paint: { "text-color": ["case", ["get", "lit"], c.card, c.accent] },
                },
            ],
        };
    };

    /** Where a feature's label and mark go: its point, its first point, a line's middle, or an area's middle. */
    const anchorOf = (geometry) => {
        switch (geometry?.type) {
            case "Point":
                return geometry.coordinates;
            case "MultiPoint":
                return geometry.coordinates[0];
            case "LineString":
                return halfway(geometry.coordinates);
            case "MultiLineString":
                return halfway(longest(geometry.coordinates, length));
            case "Polygon":
                return centroid(geometry.coordinates[0]);
            case "MultiPolygon":
                return centroid(longest(geometry.coordinates.map((p) => p[0]), (ring) => Math.abs(area(ring))));
            case "GeometryCollection":
                return anchorOf(geometry.geometries[0]);
            default:
                return null;
        }
    };
    const longest = (items, size) => items.reduce((a, b) => (size(b) > size(a) ? b : a));
    const step = (a, b) => Math.hypot(b[0] - a[0], b[1] - a[1]);
    const length = (line) => line.slice(1).reduce((sum, p, i) => sum + step(line[i], p), 0);
    /** The point halfway along a line, by its length in degrees: near enough at the scale a line is labeled. */
    const halfway = (line) => {
        let left = length(line) / 2;
        for (let i = 1; i < line.length; i += 1) {
            const d = step(line[i - 1], line[i]);
            if (d >= left && d > 0) {
                const t = left / d;
                const [a, b] = [line[i - 1], line[i]];
                return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
            }
            left -= d;
        }
        return line[line.length - 1];
    };
    const area = (ring) => ring.slice(1).reduce((sum, p, i) => sum + ring[i][0] * p[1] - p[0] * ring[i][1], 0) / 2;
    /** A ring's centroid, or its first point if it has no area. */
    const centroid = (ring) => {
        const a = area(ring);
        if (a === 0) return ring[0];
        let [x, y] = [0, 0];
        for (let i = 1; i < ring.length; i += 1) {
            const cross = ring[i - 1][0] * ring[i][1] - ring[i][0] * ring[i - 1][1];
            x += (ring[i - 1][0] + ring[i][0]) * cross;
            y += (ring[i - 1][1] + ring[i][1]) * cross;
        }
        return [x / (6 * a), y / (6 * a)];
    };

    /** Every coordinate in a GeoJSON geometry, as [longitude, latitude] pairs. */
    const points = (geometry) => {
        if (!geometry) return [];
        if (geometry.type === "GeometryCollection") return geometry.geometries.flatMap(points);
        const flat = (c) => (typeof c[0] === "number" ? [c] : c.flatMap(flat));
        return flat(geometry.coordinates);
    };

    /** A screen that keeps few WebGL contexts, a phone's, and how many maps a page keeps drawn at once on each. */
    const phone = matchMedia("(max-width: 600px)");
    const limit = () => (phone.matches ? 1 : 4);
    /** Each map the page draws: its element, data, and settings; its map while drawn; its view when put away. */
    const all = [];

    /** Draws a map that has come into view, where it was left when it was last put away. */
    const start = (entry) => {
        const { element, settings } = entry;
        const map = new maplibregl.Map({
            container: element,
            style: styleOf(entry),
            center: entry.view?.center ?? [0, 20],
            zoom: entry.view?.zoom ?? 0.6,
            renderWorldCopies: false,
            cooperativeGestures: true,
            attributionControl: { compact: true, customAttribution: "Natural Earth" },
        });
        map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
        map.addControl(new maplibregl.ScaleControl({ maxWidth: 96 }), "bottom-left");
        if (settings.popups || settings.places) pickable(map, entry);
        if (settings.places) {
            map.addControl(new BoxControl(entry), "top-right");
            boxable(map, entry);
            map.on("moveend", () => reportSpots(entry));
            map.once("idle", () => markThreads(entry));
        }
        if (entry.target) {
            // Asked to show a place while it was put away: drawn there.
            fly(entry, entry.target, 0);
            entry.target = null;
        } else if (!entry.view && settings.bounds) {
            map.fitBounds(settings.bounds, { padding: 48, maxZoom: settings.maxZoom ?? MAX_ZOOM, duration: 0 });
        }
        map.once("idle", () => {
            // On a narrow map the credits would cover it: they fold into their button, and the figure's source
            // line, under the map, credits the same.
            if (element.clientWidth < NARROW) {
                element.querySelector(".maplibregl-ctrl-attrib")?.classList.remove("maplibregl-compact-show");
            }
            element.dataset.drawn = "";
        });
        element.louvreMap = map;
        entry.map = map;
        entry.drawn(map);
    };

    /** Puts a map out of view away, freeing its WebGL context for one in view. */
    const release = (entry) => {
        entry.boxing = false;
        entry.from = null;
        entry.view = { center: entry.map.getCenter(), zoom: entry.map.getZoom() };
        entry.map.remove();
        entry.map = null;
        delete entry.element.louvreMap;
        delete entry.element.dataset.drawn;
    };

    /** Keeps drawn the maps in view, as many as the screen keeps, putting away those out of view to make room. */
    const refresh = () => {
        let live = all.filter((e) => e.map).length;
        const waiting = all.filter((e) => e.visible && !e.map).length;
        for (const entry of all) {
            if (live + waiting <= limit()) break;
            if (entry.map && !entry.visible) {
                release(entry);
                live -= 1;
            }
        }
        for (const entry of all) {
            if (live >= limit()) break;
            if (entry.visible && !entry.map) {
                start(entry);
                live += 1;
            }
        }
    };

    const seen = new IntersectionObserver((changes) => {
        for (const change of changes) {
            const entry = all.find((e) => e.element === change.target);
            if (entry) entry.visible = change.isIntersecting;
        }
        refresh();
    });
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
        for (const entry of all) entry.map?.setStyle(styleOf(entry));
    });
    phone.addEventListener("change", refresh);

    /** Reads GeoJSON given inline or as a file beside the page, as a collection of features. */
    const collection = async (given) => {
        const read = typeof given === "string" ? await (await fetch(given)).json() : given;
        if (!read) return [];
        if (read.type === "FeatureCollection") return read.features;
        return [read.type === "Feature" ? read : { geometry: read }];
    };

    /** The box around every coordinate, as [west, south, east, north], or null if there are none. */
    const boundsOf = (features) => {
        const box = [Infinity, Infinity, -Infinity, -Infinity];
        for (const [lon, lat] of features.flatMap((f) => points(f.geometry))) {
            box[0] = Math.min(box[0], lon);
            box[1] = Math.min(box[1], lat);
            box[2] = Math.max(box[2], lon);
            box[3] = Math.max(box[3], lat);
        }
        return box[0] === Infinity ? null : box;
    };

    /** Shows a feature's label and properties when a reader taps it, the label linking to its row under the map. */
    const pickable = (map, entry) => {
        const layers = ["points", "edges", "areas"];
        const label = entry.settings.label ?? "name";
        map.on("click", (event) => {
            // A box just drawn ends with its pointer let go, which is no tap.
            if (entry.boxing || entry.boxed) return;
            const { x, y } = event.point;
            const box = [
                [x - REACH, y - REACH],
                [x + REACH, y + REACH],
            ];
            // A decision's option's place is lit, never a thread to open.
            const marked = entry.settings.places ? map.queryRenderedFeatures(box, { layers: ["thread-marks"] }) : [];
            const [thread] = marked.filter((f) => f.properties.state !== "passage");
            // A feature a later version changed, while versions are compared, is its change's note to open.
            const [changed] = entry.settings.places ? map.queryRenderedFeatures(box, { layers: CHANGED }) : [];
            const tapped = thread ?? changed;
            if (tapped) {
                document.dispatchEvent(new CustomEvent("louvre:click", { detail: { id: tapped.properties.id } }));
                return;
            }
            const [hit] = map.queryRenderedFeatures(box, { layers });
            if (entry.settings.places) {
                sketch(entry, null);
                pick(entry, event, hit);
            }
            if (!hit) return;
            const index = hit.properties[INDEX];
            const feature = entry.data.features[index - 1];
            // The popup's words are drawn by its stylesheet, not written in the page, so they are no passage of
            // it: a thread's passage is found in the feature's row under the map, which says the same.
            const content = document.createElement("div");
            content.className = "louvre-popup";
            const name = document.createElement("b");
            const link = document.createElement("a");
            link.href = `#f-${index}`;
            link.dataset.text = String(feature.properties[label] ?? `Feature ${index}`);
            const row = () => document.getElementById(`f-${index}`)?.scrollIntoView({ block: "center" });
            link.addEventListener("click", row);
            name.append(link);
            const facts = document.createElement("dl");
            for (const [key, value] of Object.entries(feature.properties)) {
                const kits = key === "focus" || key === "mark" || key.startsWith("louvre:");
                if (key === label || kits || value == null) continue;
                const term = document.createElement("dt");
                term.dataset.text = key;
                const told = document.createElement("dd");
                told.dataset.text = typeof value === "object" ? JSON.stringify(value) : String(value);
                facts.append(term, told);
            }
            content.append(name, facts);
            const popup = new maplibregl.Popup({ maxWidth: "none", focusAfterOpen: false });
            popup.setLngLat(event.lngLat).setDOMContent(content).addTo(map);
        });
        for (const layer of layers) {
            map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
            map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
        }
    };

    /** Tells the bridge what a reader tapped, a feature or a point, to comment on, and where on the page it is. */
    const pick = (entry, event, hit) => {
        const box = entry.element.getBoundingClientRect();
        const { x, y } = event.point;
        const at = { top: box.top + scrollY + y - REACH, bottom: box.top + scrollY + y + REACH };
        const side = { left: box.left + x - REACH, right: box.left + x + REACH };
        // A feature is named by the id Louvre gave it; a tap off every feature is a point.
        const id = hit?.properties[PLACE_ID];
        const label = entry.settings.label ?? "name";
        const place = id
            ? { kind: "feature", id, coordinates: null }
            : { kind: "point", id: "", coordinates: [event.lngLat.lng, event.lngLat.lat] };
        const words = id ? String(hit.properties[label] ?? id) : pointWords(event.lngLat);
        const detail = { place, words, ...at, ...side };
        document.dispatchEvent(new CustomEvent("louvre:pick", { detail }));
    };

    /** The button that starts drawing a box on a map that takes places, and stops it before the box is drawn. */
    class BoxControl {
        constructor(entry) {
            this.entry = entry;
        }

        onAdd() {
            this.group = document.createElement("div");
            this.group.className = "maplibregl-ctrl maplibregl-ctrl-group";
            const button = document.createElement("button");
            button.type = "button";
            button.className = "louvre-box";
            button.title = "Draw a box to comment on";
            button.setAttribute("aria-label", "Draw a box to comment on");
            button.setAttribute("aria-pressed", "false");
            button.addEventListener("click", () => boxing(this.entry, !this.entry.boxing));
            this.group.append(button);
            return this.group;
        }

        onRemove() {
            this.group.remove();
        }
    }

    /** Starts or stops drawing a box: while drawing, a drag draws the box rather than moving the map. */
    const boxing = (entry, on) => {
        const { map } = entry;
        if (!map) return;
        entry.boxing = on;
        entry.from = null;
        entry.element.querySelector("button.louvre-box")?.setAttribute("aria-pressed", String(on));
        map.getCanvasContainer().classList.toggle("louvre-boxing", on);
        if (on) map.dragPan.disable();
        else map.dragPan.enable();
    };

    /** Lets a reader draw a box on the map, by a drag from one corner to the other, once the box button is pressed. */
    const boxable = (map, entry) => {
        const canvas = map.getCanvasContainer();
        const at = (event) => {
            const box = canvas.getBoundingClientRect();
            return [event.clientX - box.left, event.clientY - box.top];
        };
        canvas.addEventListener("pointerdown", (event) => {
            if (!entry.boxing || !event.isPrimary) return;
            // Kept from the map, which would move, and from the page, which would select its words.
            event.preventDefault();
            canvas.setPointerCapture(event.pointerId);
            entry.from = at(event);
        });
        canvas.addEventListener("pointermove", (event) => {
            if (entry.from) sketch(entry, cornersOf(map, entry.from, at(event)));
        });
        const end = (event) => {
            if (!entry.from) return;
            const [a, b] = [entry.from, at(event)];
            boxing(entry, false);
            entry.boxed = true;
            setTimeout(() => (entry.boxed = false));
            // A drag too short to be a box is no box: it leaves nothing drawn.
            const corners = cornersOf(map, a, b);
            if (event.type === "pointercancel" || Math.abs(a[0] - b[0]) < REACH || Math.abs(a[1] - b[1]) < REACH) {
                sketch(entry, null);
                return;
            }
            sketch(entry, corners);
            pickBox(entry, corners, a, b);
        };
        canvas.addEventListener("pointerup", end);
        canvas.addEventListener("pointercancel", end);
    };

    // Escape stops drawing a box, and takes away one half drawn.
    document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") return;
        for (const entry of all) {
            if (!entry.boxing) continue;
            sketch(entry, null);
            boxing(entry, false);
        }
    });

    /** The box between two points on a map's screen, as [west, south, east, north], to five places as it is said. */
    const cornersOf = (map, a, b) => {
        const [p, q] = [map.unproject(a), map.unproject(b)];
        const round = (v) => Math.round(v * 1e5) / 1e5;
        const clamp = (v, most) => Math.max(-most, Math.min(most, v));
        const [west, east] = [Math.min(p.lng, q.lng), Math.max(p.lng, q.lng)].map((v) => round(clamp(v, 180)));
        const [south, north] = [Math.min(p.lat, q.lat), Math.max(p.lat, q.lat)].map((v) => round(clamp(v, 90)));
        return [west, south, east, north];
    };

    /** A box as GeoJSON: a Polygon from its south-west corner, anticlockwise. */
    const boxShape = ([west, south, east, north]) => ({
        type: "Polygon",
        coordinates: [
            [
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south],
            ],
        ],
    });

    /** Draws the box being drawn, or drawn and not yet commented on; none when `corners` is null. */
    const sketch = (entry, corners) => {
        entry.sketched = corners;
        const features = corners ? [{ type: "Feature", properties: {}, geometry: boxShape(corners) }] : [];
        entry.sketch = { type: "FeatureCollection", features };
        entry.map?.getSource("sketch")?.setData(entry.sketch);
    };

    /** Tells the bridge a reader drew a box to comment on, and where on the page it is. */
    const pickBox = (entry, corners, a, b) => {
        const box = entry.element.getBoundingClientRect();
        const [west, south, east, north] = corners;
        const at = { top: box.top + scrollY + Math.min(a[1], b[1]), bottom: box.top + scrollY + Math.max(a[1], b[1]) };
        const side = { left: box.left + Math.min(a[0], b[0]), right: box.left + Math.max(a[0], b[0]) };
        const words = `${pointWords({ lng: west, lat: south })} to ${pointWords({ lng: east, lat: north })}`;
        const detail = { place: { kind: "box", id: "", coordinates: corners }, words, ...at, ...side };
        document.dispatchEvent(new CustomEvent("louvre:pick", { detail }));
    };

    /** Says a point as Louvre quotes one: its latitude, then its longitude, to five places. */
    const pointWords = ({ lng, lat }) =>
        `${Math.abs(lat).toFixed(5)}° ${lat >= 0 ? "N" : "S"}, ${Math.abs(lng).toFixed(5)}° ${lng >= 0 ? "E" : "W"}`;

    /** Marks each thread on a place on a map that takes them, as the bridge last asked, and says where each sits. */
    const markThreads = (entry) => {
        const at = new Map(entry.anchors.features.map((a) => [a.properties[PLACE_ID], a.geometry.coordinates]));
        const features = [];
        const boxes = [];
        const reach = [];
        const spots = [];
        for (const mark of threadMarks) {
            const { kind, coordinates: given } = mark.place;
            const corner = kind === "box" ? [given[0], given[3]] : null;
            const coordinates = kind === "point" ? given : corner ?? at.get(mark.place.id);
            if (!coordinates) continue;
            spots.push({ id: mark.id, coordinates });
            // A decision's option's place is drawn only while its option is hovered or focused.
            if (mark.state === "passage" && !mark.lit) continue;
            const n = mark.n === null ? "" : String(mark.n);
            const properties = { id: mark.id, n, state: mark.state, lit: mark.lit };
            features.push({ type: "Feature", properties, geometry: { type: "Point", coordinates } });
            if (kind === "box") boxes.push({ type: "Feature", properties, geometry: boxShape(given) });
            if (kind === "point" && mark.place.accuracy > 0) {
                reach.push({ type: "Feature", properties, geometry: around(given, mark.place.accuracy) });
            }
            // A box drawn is drawn as its thread, or its draft, once there is one.
            if (kind === "box" && String(given) === String(entry.sketched)) sketch(entry, null);
        }
        const changed = [];
        const was = [];
        const moves = [];
        for (const change of changeMarks) {
            const properties = { id: change.mark, lit: change.lit };
            const feature = (geometry) => ({ type: "Feature", properties, geometry });
            const now = change.kind === "removed" ? null : change.geometry;
            const then = change.kind === "removed" ? change.geometry : change.was;
            if (now) changed.push(feature(now));
            if (then) was.push(feature(then));
            const [from, to] = [anchorOf(then), anchorOf(now)];
            if (from && to) moves.push(feature({ type: "LineString", coordinates: [from, to] }));
            const spot = to ?? from;
            if (spot) spots.push({ id: change.mark, coordinates: spot });
        }
        entry.threads = { type: "FeatureCollection", features };
        entry.boxes = { type: "FeatureCollection", features: boxes };
        entry.reach = { type: "FeatureCollection", features: reach };
        entry.changed = { type: "FeatureCollection", features: changed };
        entry.was = { type: "FeatureCollection", features: was };
        entry.moves = { type: "FeatureCollection", features: moves };
        entry.spots = spots;
        for (const name of ["threads", "boxes", "reach", "changed", "was", "moves"]) {
            entry.map?.getSource(name)?.setData(entry[name]);
        }
        reportSpots(entry);
    };

    /** A ring `metres` around a point on the earth, as a Polygon: near enough round at the scale a reading has. */
    const around = ([lon, lat], metres) => {
        const rise = ((metres / EARTH) * 180) / Math.PI;
        const run = rise / Math.max(Math.cos((lat * Math.PI) / 180), 0.01);
        const ring = Array.from({ length: 65 }, (_, i) => {
            const turn = (i % 64) * ((2 * Math.PI) / 64);
            return [lon + run * Math.cos(turn), lat + rise * Math.sin(turn)];
        });
        return { type: "Polygon", coordinates: [ring] };
    };

    /** The box around a mark the bridge asked for, by its id: a place's, or a change's, where it was and is now. */
    const boxOfMark = (entry, id) => {
        const mark = threadMarks.find((m) => m.id === id);
        if (mark?.place.kind === "box") return mark.place.coordinates;
        if (mark?.place.kind === "point") {
            const [lon, lat] = mark.place.coordinates;
            const ring = mark.place.accuracy > 0 ? around([lon, lat], mark.place.accuracy) : null;
            return ring ? boundsOf([{ geometry: ring }]) : [lon, lat, lon, lat];
        }
        if (mark) {
            const feature = entry.data.features.find((f) => f.properties[PLACE_ID] === mark.place.id);
            return feature ? boundsOf([feature]) : null;
        }
        const change = changeMarks.find((c) => c.mark === id);
        return change ? boundsOf([{ geometry: change.geometry }, { geometry: change.was }]) : null;
    };

    /**
     * Pans and zooms a map to a box, as near as a street unless it is nearer already: over `duration` ms, or as a
     * flight, which jumps there instead when it would take longer than `FLIGHT` ms.
     */
    const fly = (entry, box, duration) => {
        const most = Math.max(entry.map.getZoom(), Math.min(entry.settings.maxZoom ?? MAX_ZOOM, SHOW_ZOOM));
        const timing = duration === undefined ? { maxDuration: FLIGHT } : { duration };
        entry.map.fitBounds(box, { padding: 64, maxZoom: most, ...timing });
    };

    // The bridge asks a map to show a place, as a decision's option's link does: the map pans and zooms to it, there
    // and then if it is drawn, or once it is.
    document.addEventListener("louvre:show", (event) => {
        const id = event.detail?.id;
        for (const entry of all) {
            if (!entry.settings.places || typeof id !== "string") continue;
            const box = boxOfMark(entry, id);
            if (!box) continue;
            if (entry.map) fly(entry, box);
            else entry.target = box;
        }
    });

    /** Tells the bridge where each thread on this map sits, from the map's top, while it is on the map in view. */
    const reportSpots = (entry) => {
        // While the map moves its spots move with it: they are told once it stops, as each move ends, so the page is
        // not laid out again at every frame of a pan.
        if (!entry.map || entry.map.isMoving()) return;
        const height = entry.element.clientHeight;
        const width = entry.element.clientWidth;
        const spots = {};
        for (const spot of entry.spots) {
            const p = entry.map.project(spot.coordinates);
            if (p.x >= 0 && p.x <= width && p.y >= 0 && p.y <= height) {
                spots[spot.id] = { top: p.y - REACH, bottom: p.y + REACH };
            }
        }
        document.dispatchEvent(new CustomEvent("louvre:spots", { detail: { map: entry.element, spots } }));
    };

    /** The threads and options on places the bridge last asked the maps to mark, and the features changed. */
    let threadMarks = [];
    let changeMarks = [];
    /** The hue the bridge marks what a later version changed in, as `#rrggbb`; empty until it says. */
    let changeHue = "";
    document.addEventListener("louvre:marks", (event) => {
        const { marks, changes, hue } = event.detail ?? {};
        threadMarks = Array.isArray(marks) ? marks : [];
        changeMarks = Array.isArray(changes) ? changes : [];
        const recolor = typeof hue === "string" && hue !== changeHue;
        if (recolor) changeHue = hue;
        for (const entry of all) {
            if (!entry.settings.places) continue;
            if (recolor) entry.map?.setStyle(styleOf(entry));
            markThreads(entry);
        }
    });

    /** Draws `options.data` in `where` once it is in view; resolves to its MapLibre map, the first time it is drawn. */
    const draw = async (where, options = {}) => {
        const element = typeof where === "string" ? document.getElementById(where) : where;
        const features = (await collection(options.data)).map((f, i) => ({
            ...f,
            type: "Feature",
            properties: { ...(f.properties ?? {}), [INDEX]: i + 1 },
        }));
        const context = { type: "FeatureCollection", features: await collection(options.context) };
        const bounds = boundsOf(features);
        const middle = bounds ? (bounds[0] + bounds[2]) / 2 : 0;
        const label = options.label ?? "name";
        // One anchor to a feature, where its label and its mark go, so a trace in parts is named once.
        const anchors = features.flatMap((f) => {
            const at = anchorOf(f.geometry);
            if (!at) return [];
            const properties = { ...f.properties, [LABEL]: String(f.properties[label] ?? ""), [EAST]: at[0] > middle };
            return [{ type: "Feature", properties, geometry: { type: "Point", coordinates: at } }];
        });
        const focusAll = !features.some((f) => "focus" in f.properties);
        return new Promise((drawn) => {
            all.push({
                element,
                data: { type: "FeatureCollection", features },
                anchors: { type: "FeatureCollection", features: anchors },
                threads: { type: "FeatureCollection", features: [] },
                boxes: { type: "FeatureCollection", features: [] },
                sketch: { type: "FeatureCollection", features: [] },
                reach: { type: "FeatureCollection", features: [] },
                changed: { type: "FeatureCollection", features: [] },
                was: { type: "FeatureCollection", features: [] },
                moves: { type: "FeatureCollection", features: [] },
                spots: [],
                target: null,
                sketched: null,
                boxing: false,
                from: null,
                boxed: false,
                context,
                settings: { ...options, focusAll, bounds },
                map: null,
                visible: false,
                drawn,
            });
            seen.observe(element);
        });
    };

    window.LouvreMap = { version: "louvre-map-1", draw };
})();
