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
    const tops: number[] = items.map(() => 0)
    const top = (k: number) => tops[k] ?? 0
    const height = (k: number) => items[k]?.height ?? 0
    const want = (k: number) => items[k]?.want ?? 0
    const forward = (from: number) => {
        for (let k = from; k < items.length; k++) {
            const floor = k > 0 ? top(k - 1) + height(k - 1) + gap : 0
            tops[k] = Math.max(want(k), floor)
        }
    }
    const at = items.findIndex((item) => item.id === active)
    if (at < 0) {
        forward(0)
        return tops
    }
    tops[at] = Math.max(want(at), 0)
    forward(at + 1)
    for (let k = at - 1; k >= 0; k--) {
        tops[k] = Math.min(want(k), top(k + 1) - height(k) - gap)
    }
    if (top(0) < 0) {
        tops[0] = 0
        forward(1)
    }
    return tops
}
