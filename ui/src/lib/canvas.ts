// A board's canvas: where its frames are, and the view of them a reader pans and zooms.
//
// A view maps the canvas onto the screen: a point (cx, cy) on the canvas is drawn at (x + cx * scale, y + cy *
// scale) in the viewport. Every change keeps the scale within its bounds.

/** How far a reader zooms out, and in, as the scale of the canvas on the screen. */
export const MIN_SCALE = 0.05
/**
 * See MIN_SCALE: a frame's page at its own size, which a reader opens the frame to read closer. Past it, WebKit, every
 * iPhone browser's engine, draws each page at the zoom times the screen's density: a laptop's page at 2 on a phone's
 * screen is some 190 MB.
 */
export const MAX_SCALE = 1
/** How much one press of a zoom control zooms. */
export const ZOOM_STEP = 1.25
/** The longest a phone's screen is on its shorter side, in screen pixels, as ui/DESIGN.md has it. */
export const PHONE = 600
/**
 * How many frames' pages a phone draws live at most, at any zoom: six pages at once are more than its browser has the
 * memory for. Two zoomed out cost less than two zoomed in, as each is drawn at the zoom times the screen's density.
 */
export const LIVE_COUNT = 2

/** How the canvas is drawn on the screen: its offset, and its scale. */
export interface View {
    /** Where the canvas's left edge is, from the viewport's, in screen pixels. */
    x: number
    /** Where the canvas's top edge is, from the viewport's, in screen pixels. */
    y: number
    /** Screen pixels a canvas pixel takes. */
    scale: number
}

/** A rectangle, on the canvas or the screen. */
export interface Box {
    /** Its left edge. */
    x: number
    /** Its top edge. */
    y: number
    /** Its width. */
    width: number
    /** Its height. */
    height: number
}

/** A point, on the screen. */
export interface Point {
    /** From the viewport's left edge. */
    x: number
    /** From the viewport's top edge. */
    y: number
}

/** The box that holds every box given, grown by `margin` on its top for their labels; empty for none. */
export function bounds(boxes: readonly Box[], margin = 0): Box {
    if (boxes.length === 0) {
        return { x: 0, y: 0, width: 0, height: 0 }
    }
    const left = Math.min(...boxes.map((b) => b.x))
    const top = Math.min(...boxes.map((b) => b.y)) - margin
    const right = Math.max(...boxes.map((b) => b.x + b.width))
    const bottom = Math.max(...boxes.map((b) => b.y + b.height))
    return { x: left, y: top, width: right - left, height: bottom - top }
}

/** The view that shows all of `world` in a viewport of `width` by `height`, centered, with `padding` around it. */
export function fit(world: Box, width: number, height: number, padding: number): View {
    const room = { width: Math.max(width - 2 * padding, 1), height: Math.max(height - 2 * padding, 1) }
    const scale = clamp(Math.min(room.width / Math.max(world.width, 1), room.height / Math.max(world.height, 1)))
    return {
        x: (width - world.width * scale) / 2 - world.x * scale,
        y: (height - world.height * scale) / 2 - world.y * scale,
        scale,
    }
}

/** Zoom by `factor` about a point on the screen, which stays where it is: the cursor, or a pinch's middle. */
export function zoomAt(view: View, factor: number, at: Point): View {
    const scale = clamp(view.scale * factor)
    const applied = scale / view.scale
    return { x: at.x - (at.x - view.x) * applied, y: at.y - (at.y - view.y) * applied, scale }
}

/** Move the canvas by `dx` and `dy` screen pixels. */
export function panBy(view: View, dx: number, dy: number): View {
    return { ...view, x: view.x + dx, y: view.y + dy }
}

/**
 * The boxes whose pages are drawn live at a view, on a screen `width` by `height`: on a phone's, the LIVE_COUNT the
 * screen shows the most of, the most shown first and the board's order between equals; on any other, every one.
 */
export function live<T extends Box>(boxes: readonly T[], view: View, width: number, height: number): T[] {
    if (Math.min(width, height) > PHONE) {
        return [...boxes]
    }
    return (
        boxes
            // Rounded, so frames the screen shows alike keep the board's order rather than a rounding error's.
            .map((box) => ({ box, shown: Math.round(shownArea(box, view, width, height)) }))
            .filter(({ shown }) => shown > 0)
            .toSorted((a, b) => b.shown - a.shown)
            .slice(0, LIVE_COUNT)
            .map(({ box }) => box)
    )
}

/** How much a wheel's turn zooms: in for a turn up, out for one down; a trackpad's pinch, with ctrl, more finely. */
export function wheelFactor(deltaY: number, deltaMode: number, ctrlKey: boolean): number {
    // A line is about 16 pixels, a page about 800: a mouse's notch and a trackpad's scroll then zoom alike.
    const pixels = deltaY * (deltaMode === 1 ? 16 : deltaMode === 2 ? 800 : 1)
    return Math.exp(-pixels * (ctrlKey ? 0.01 : 0.002))
}

/** How much of a box is on a screen `width` by `height` at a view, in screen pixels. */
function shownArea(box: Box, view: View, width: number, height: number): number {
    const left = Math.max(view.x + box.x * view.scale, 0)
    const right = Math.min(view.x + (box.x + box.width) * view.scale, width)
    const top = Math.max(view.y + box.y * view.scale, 0)
    const bottom = Math.min(view.y + (box.y + box.height) * view.scale, height)
    return Math.max(right - left, 0) * Math.max(bottom - top, 0)
}

function clamp(scale: number): number {
    return Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale))
}
