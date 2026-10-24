/* louvre-map-1: draws a map in Louvre's style, with MapLibre GL JS and a basemap from Natural Earth. */
/* LouvreMap.draw(element or its id, {data, context, label, maxZoom}) draws `data`, GeoJSON or a file beside the */
/* page, on the basemap: a feature whose `focus` is true in the accent and the rest muted, or every one in the */
/* accent when none is; each labeled once with the property `label` names, "name" unless said, and numbered with */
/* its `mark` if it has one. `context`, GeoJSON or a file too, such as streets or kerbs, is drawn quietly under it. */
/* The basemap is a city's scale at most: zoomed in past it, it fades to plain ground, and the context places the */
/* data. A map is drawn while it is in view, and put away out of view when another needs its WebGL context. */
(() => {
    const base = new URL(".", document.currentScript.src).href;
    const css = /* maplibre-gl.css */ "";
    const font = ["Noto Sans Regular"];
    const italic = ["Noto Sans Italic"];
    /** The property the kit gives each place east of the map's middle, whose label goes west of it first. */
    const EAST = "louvre:east";
    /** The property holding the label the kit gives each feature's anchor. */
    const LABEL = "louvre:label";
    /** The zoom past which the basemap has faded to plain ground: about a city's, Natural Earth's finest. */
    const DETAIL = 11;
    /** How narrow a map is, in CSS pixels, for its credits to fold away: a phone's. */
    const NARROW = 480;
    /** How far in a map zooms to fit its data, unless the page says: a few streets. */
    const MAX_ZOOM = 17;
    /** A label's sides under its place and over it, as MapLibre's anchors and offsets, in ems. */
    const UNDER_OVER = ["top", [0, 0.75], "bottom", [0, -0.75]];

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
        const color = ["case", focus, c.accent, c.muted];
        const ground = mix(c.card, c.rule, 0.55);
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
                        "circle-color": ["case", focus, c.accent, c.bg],
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
        if (!entry.view && settings.bounds) {
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

    /** Draws `options.data` in `where` once it is in view; resolves to its MapLibre map, the first time it is drawn. */
    const draw = async (where, options = {}) => {
        const element = typeof where === "string" ? document.getElementById(where) : where;
        const features = (await collection(options.data)).map((f) => ({ type: "Feature", properties: {}, ...f }));
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
