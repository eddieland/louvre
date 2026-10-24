/* louvre-map-1: draws a map in Louvre's style, with MapLibre GL JS and a basemap from Natural Earth. */
/* LouvreMap.draw(element or its id, {data, label, maxZoom}) draws `data`, GeoJSON or a file beside the page, on the */
/* basemap: a feature whose `focus` is true in the accent and the rest muted, or every one in the accent when none */
/* is; each labeled with the property `label` names, "name" unless said, and numbered with its `mark` if it has one. */
/* A map is drawn while it is in view, and put away out of view when another needs its WebGL context. */
(() => {
    const base = new URL(".", document.currentScript.src).href;
    const css = /* maplibre-gl.css */ "";
    const font = ["Noto Sans Regular"];
    const italic = ["Noto Sans Italic"];
    /** The property the kit gives each place east of the map's middle, whose label goes west of it first. */
    const EAST = "louvre:east";
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
        filter: ["all", [">=", ["get", "scalerank"], ranks[0]], ["<=", ["get", "scalerank"], ranks[1]]],
        layout: {
            "text-field": ["get", "name"],
            "text-font": italic,
            "text-size": 10.5,
            "symbol-sort-key": ["get", "scalerank"],
        },
        paint: { "text-color": mix(c.muted, c.card, 0.3), "text-halo-color": c.card, "text-halo-width": 1 },
    });

    /** The map's style: the basemap from the kit, in the page's colors, and the page's data over it. */
    const styleOf = (data, options) => {
        const c = tokens();
        const focus = ["case", ["has", "focus"], ["get", "focus"], options.focusAll];
        const color = ["case", focus, c.accent, c.muted];
        const label = options.label ?? "name";
        const kit = (name) => ({ type: "geojson", data: `${base}basemap/${name}.json` });
        return {
            version: 8,
            glyphs: `${base}glyphs/{fontstack}/{range}.pbf`,
            sources: {
                land: kit("land"),
                lakes: kit("lakes"),
                borders: kit("borders"),
                places: kit("places"),
                data: { type: "geojson", data },
            },
            layers: [
                { id: "water", type: "background", paint: { "background-color": c.bg } },
                { id: "land", type: "fill", source: "land", paint: { "fill-color": mix(c.card, c.rule, 0.55) } },
                { id: "lakes", type: "fill", source: "lakes", paint: { "fill-color": c.bg } },
                {
                    id: "borders",
                    type: "line",
                    source: "borders",
                    paint: { "line-color": mix(c.rule, c.muted, 0.3), "line-width": 0.75 },
                },
                places("places", [0, 2], 2.5, c),
                places("places-more", [3, 5], 5, c),
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
                    paint: { "line-color": color, "line-width": ["case", focus, 2, 1.25] },
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
                    source: "data",
                    layout: {
                        "text-field": ["coalesce", ["get", label], ""],
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
                    source: "data",
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
        const { element, data, settings } = entry;
        const map = new maplibregl.Map({
            container: element,
            style: styleOf(data, settings),
            center: entry.view?.center ?? [0, 20],
            zoom: entry.view?.zoom ?? 0.6,
            renderWorldCopies: false,
            cooperativeGestures: true,
            attributionControl: { compact: true, customAttribution: "Natural Earth" },
        });
        map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
        map.addControl(new maplibregl.ScaleControl({ maxWidth: 96 }), "bottom-left");
        if (!entry.view && settings.bounds) {
            map.fitBounds(settings.bounds, { padding: 48, maxZoom: settings.maxZoom ?? 6, duration: 0 });
        }
        map.once("idle", () => {
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
        for (const entry of all) entry.map?.setStyle(styleOf(entry.data, entry.settings));
    });
    phone.addEventListener("change", refresh);

    /** Draws `options.data` in `where` once it is in view; resolves to its MapLibre map, the first time it is drawn. */
    const draw = async (where, options = {}) => {
        const element = typeof where === "string" ? document.getElementById(where) : where;
        const given = options.data ?? { type: "FeatureCollection", features: [] };
        const read = typeof given === "string" ? await (await fetch(given)).json() : given;
        const features = read.type === "FeatureCollection" ? read.features : [read];
        const coordinates = features.flatMap((f) => points(f.geometry));
        const lons = coordinates.map((p) => p[0]);
        const lats = coordinates.map((p) => p[1]);
        const bounds = coordinates.length
            ? [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)]
            : null;
        const middle = bounds ? (bounds[0] + bounds[2]) / 2 : 0;
        const east = (f) => f.geometry?.type === "Point" && f.geometry.coordinates[0] > middle;
        const data = {
            type: "FeatureCollection",
            features: features.map((f) => ({ ...f, properties: { ...f.properties, [EAST]: east(f) } })),
        };
        const focusAll = !features.some((f) => f.properties && "focus" in f.properties);
        const settings = { ...options, focusAll, bounds };
        return new Promise((drawn) => {
            all.push({ element, data, settings, map: null, visible: false, drawn });
            seen.observe(element);
        });
    };

    window.LouvreMap = { version: "louvre-map-1", draw };
})();
