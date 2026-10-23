// Where each thread sits in the margin: level with its passage, moved aside when it would overlap another
// (ui/DESIGN.md, "Threads"). The active thread keeps its place, and the others move up or down from it.

/** A thread to place: where it wants to sit, and how tall it is. */
export interface Item {
    /** The thread's id. */
    id: string
    /** The top of its passage, in the margin's pixels. */
    want: number
    /** Its height as drawn. */
    height: number
}

/** The space between two threads, in pixels. */
export const GAP = 12

/**
 * Place threads, given in page order: each at its passage, or below the one before it; with an active thread, it
 * at its passage, those after it below, those before it above, and all of them pushed down if that leaves the top.
 */
export function place(items: readonly Item[], active: string | null, gap: number = GAP): number[] {
    const tops: number[] = Array.from({ length: items.length }, () => 0)
    const forward = (from: number, keep: boolean) => {
        for (let k = from; k < items.length; k++) {
            const item = items[k]!
            const before = items[k - 1]
            const floor = before ? tops[k - 1]! + before.height + gap : 0
            tops[k] = Math.max(keep && k === from ? tops[k]! : item.want, floor)
        }
    }
    const at = items.findIndex((item) => item.id === active)
    if (at < 0) {
        forward(0, false)
        return tops
    }
    tops[at] = Math.max(items[at]!.want, 0)
    forward(at + 1, false)
    for (let k = at - 1; k >= 0; k--) {
        tops[k] = Math.min(items[k]!.want, tops[k + 1]! - items[k]!.height - gap)
    }
    if ((tops[0] ?? 0) < 0) {
        tops[0] = 0
        forward(1, false)
    }
    return tops
}
