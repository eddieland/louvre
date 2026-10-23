// A page's text, as louvre.core.text reads it from the markup, read here from the live page, and the anchors on it.
//
// Both sides read the same text: what a reader sees, each run of whitespace one space and its ends trimmed, the
// contents of script, style, template, title, and noscript left out, and a block tag parting the words either side.
// tests/fixtures/anchors.json holds both to the same answers. This side also keeps where each character came from, so
// an anchor found in the text becomes a Range on the page, and a selection on the page becomes an anchor.

/** The most of the text either side of a passage an anchor keeps, as the server's CONTEXT. */
export const CONTEXT = 32

/** A passage: its words, and up to CONTEXT characters of the text either side, as the artifacts contract quotes one. */
export interface Anchor {
    /** The passage's own words. */
    exact: string
    /** The text before it, the nearest last. */
    prefix: string
    /** The text after it, the nearest first. */
    suffix: string
}

/** A page's text, and where on the page each of its characters is. */
export interface PageText {
    /** The text, whitespace collapsed. */
    text: string
    /** The Range of the page that the text from start to end (exclusive) covers. */
    range: (start: number, end: number) => Range | null
    /** The span of the text a Range of the page covers, or null when it covers none. */
    span: (range: Range) => { start: number; end: number } | null
}

/** Elements whose contents a page does not show. */
const HIDDEN = new Set(['script', 'style', 'template', 'title', 'noscript'])
/** Elements that sit inside a line of text, so their tags part no words: louvre.core.text's _INLINE. */
const INLINE = new Set([
    'a',
    'abbr',
    'b',
    'bdi',
    'bdo',
    'cite',
    'code',
    'data',
    'del',
    'dfn',
    'em',
    'font',
    'i',
    'ins',
    'kbd',
    'mark',
    'q',
    's',
    'samp',
    'small',
    'span',
    'strong',
    'sub',
    'sup',
    'time',
    'u',
    'var',
])
/** Whitespace as Python's str.split() takes it, near enough: JavaScript's \s. */
const SPACE = /\s/u

/** A run of the raw text: a text node's data from `at`, or one space a block tag adds. */
interface Run {
    at: number
    node: Text | null
}

/**
 * Read a page's text from `root`, skipping what `skip` says is Louvre's own (the bridge's overlay).
 */
export function readText(root: Node, skip: (element: Element) => boolean = () => false): PageText {
    const runs: Run[] = []
    let raw = ''
    const space = () => {
        runs.push({ at: raw.length, node: null })
        raw += ' '
    }
    const walk = (node: Node) => {
        for (let child = node.firstChild; child; child = child.nextSibling) {
            if (child.nodeType === Node.TEXT_NODE) {
                const text = child as Text
                runs.push({ at: raw.length, node: text })
                raw += text.data
            } else if (child.nodeType === Node.ELEMENT_NODE) {
                const element = child as Element
                const tag = element.localName
                if (HIDDEN.has(tag) || skip(element)) {
                    continue
                }
                const block = !INLINE.has(tag)
                if (block) {
                    space()
                }
                walk(element)
                if (block) {
                    space()
                }
            }
        }
    }
    walk(root)

    // Collapse: `rawOf[i]` is where the text's i'th character came from in the raw text, and `textOf[r]` where raw
    // position r lands in the text: its own character, or for whitespace the one space its run becomes.
    const rawOf: number[] = []
    const textOf = new Int32Array(raw.length + 1)
    let text = ''
    let pendingSpace = -1
    for (let r = 0; r < raw.length; r++) {
        const char = raw.charAt(r)
        if (SPACE.test(char)) {
            if (pendingSpace < 0 && text.length > 0) {
                pendingSpace = r
            }
            textOf[r] = text.length
            continue
        }
        if (pendingSpace >= 0) {
            rawOf.push(pendingSpace)
            text += ' '
            pendingSpace = -1
        }
        textOf[r] = text.length
        rawOf.push(r)
        text += char
    }
    textOf[raw.length] = text.length

    const runAt = (r: number): number => {
        let lo = 0
        let hi = runs.length - 1
        while (lo < hi) {
            const mid = (lo + hi + 1) >> 1
            if ((runs[mid]?.at ?? Infinity) <= r) {
                lo = mid
            } else {
                hi = mid - 1
            }
        }
        return lo
    }
    // The page's position of raw character r: in its text node, or the start of the next one for a block's space.
    const pointAt = (r: number, after: boolean): [Node, number] | null => {
        let i = runAt(r)
        const run = runs[i]
        if (!run) {
            return null
        }
        if (run.node) {
            return [run.node, r - run.at + (after ? 1 : 0)]
        }
        for (i += after ? -1 : 1; i >= 0 && i < runs.length; i += after ? -1 : 1) {
            const near = runs[i]
            if (near?.node) {
                return [near.node, after ? near.node.data.length : 0]
            }
        }
        return null
    }

    return {
        text,
        range(start, end) {
            const first = rawOf[start]
            const last = rawOf[end - 1]
            if (first === undefined || last === undefined || end <= start) {
                return null
            }
            const from = pointAt(first, false)
            const to = pointAt(last, true)
            if (!from || !to) {
                return null
            }
            const range = (root.ownerDocument ?? (root as Document)).createRange()
            range.setStart(from[0], from[1])
            range.setEnd(to[0], to[1])
            return range
        },
        span(range) {
            const start = rawPosition(runs, range.startContainer, range.startOffset, false)
            const end = rawPosition(runs, range.endContainer, range.endOffset, true)
            if (start === null || end === null) {
                return null
            }
            let from = textOf[start] ?? text.length
            let to = textOf[end] ?? text.length
            while (from < to && text.charAt(from) === ' ') {
                from++
            }
            while (to > from && text.charAt(to - 1) === ' ') {
                to--
            }
            return to > from ? { start: from, end: to } : null
        },
    }
}

/** Where a boundary point of a Range is in the raw text, or null when it is in no text this page reads. */
function rawPosition(runs: Run[], container: Node, offset: number, end: boolean): number | null {
    if (container.nodeType === Node.TEXT_NODE) {
        const run = runs.find((r) => r.node === container)
        return run ? run.at + offset : null
    }
    // A point between an element's children: the first text after it, or for an end the last text before it.
    const point = container.ownerDocument?.createRange()
    if (!point) {
        return null
    }
    point.setStart(container, offset)
    let found: number | null = null
    for (const run of runs) {
        if (!run.node) {
            continue
        }
        const where = point.comparePoint(run.node, 0)
        if (end && where < 0) {
            found = run.at + run.node.data.length
        } else if (!end && where >= 0) {
            return run.at
        }
    }
    return found
}

/** Collapse each run of whitespace to one space, and trim the ends, as both sides do. */
export function collapse(text: string): string {
    return text.split(/\s+/u).filter(Boolean).join(' ')
}

/** Make an anchor from its parts, each collapsed, as the server's Anchor.of does. */
export function anchorOf(exact: string, prefix = '', suffix = ''): Anchor {
    return { exact: collapse(exact), prefix: collapse(prefix), suffix: collapse(suffix) }
}

/** Quote the text from start to end as an anchor, with up to CONTEXT characters either side. */
export function quote(text: string, start: number, end: number): Anchor {
    return anchorOf(
        text.slice(start, end),
        text.slice(Math.max(0, start - CONTEXT), start),
        text.slice(end, end + CONTEXT),
    )
}

/**
 * Find where an anchor's passage starts in a page's text: the copy whose sides match best, the first of those that
 * tie, or null when its words are nowhere. louvre.core.text's locate, line for line.
 */
export function locate(text: string, anchor: Anchor): number | null {
    if (!anchor.exact) {
        return null
    }
    const prefix = anchor.prefix.trimEnd()
    const suffix = anchor.suffix.trimStart()
    let best: number | null = null
    let bestScore = -1
    let at = text.indexOf(anchor.exact)
    while (at !== -1) {
        const score = commonSuffix(text, at, prefix) + commonPrefix(text, at + anchor.exact.length, suffix)
        if (score > bestScore) {
            best = at
            bestScore = score
            if (score === prefix.length + suffix.length) {
                break
            }
        }
        at = text.indexOf(anchor.exact, at + 1)
    }
    return best
}

/** How many characters the text before `end` ends with of what `want` ends with, its whitespace at `end` aside. */
function commonSuffix(text: string, end: number, want: string): number {
    let i = end
    while (i > 0 && SPACE.test(text.charAt(i - 1))) {
        i--
    }
    let n = 0
    while (n < i && n < want.length && text.charAt(i - 1 - n) === want.charAt(want.length - 1 - n)) {
        n++
    }
    return n
}

/** How many characters the text from `start` starts with of what `want` starts with, its whitespace aside. */
function commonPrefix(text: string, start: number, want: string): number {
    let i = start
    while (i < text.length && SPACE.test(text.charAt(i))) {
        i++
    }
    let n = 0
    while (i + n < text.length && n < want.length && text.charAt(i + n) === want.charAt(n)) {
        n++
    }
    return n
}
