// The messages between the artifact page and the bridge inside its sandboxed frame.
//
// The frame has an opaque origin, so its messages arrive from origin "null" and are sent to it with "*": the page
// checks instead that a message came from its own frame's window, and that it has this shape. The artifact's own
// scripts share the frame's window and can send the same messages; they can only say where a passage is or what was
// selected, which the person still acts on themselves, so nothing a message says is trusted further than that.

import type { Anchor } from './text'

/** The tag every message carries, with the protocol's version. */
export const CHANNEL = 'louvre:bridge/1'

/** A thread's passage, or a change's, as the page asks the bridge to mark it. */
export interface Mark {
    /** The thread's id, a draft's, or a change's. */
    id: string
    /** The passage. */
    anchor: Anchor
    /**
     * A thread open, resolved, or a draft not yet sent; or words a later version added or rewrote (`change`), or the
     * word beside where it removed some (`removed`), which is found, to place its note, but never painted.
     */
    state: 'open' | 'resolved' | 'draft' | 'change' | 'removed'
    /** Its number in the margin, shown after its last word, or null for none. */
    n: number | null
}

/** The colors the bridge marks passages in: the page's tokens, so the marks follow Louvre's theme. */
export interface Colors {
    /** A passage at rest. */
    rest: string
    /** A passage hovered or active. */
    strong: string
    /** A resolved passage hovered or active. */
    resolved: string
    /** A thread's number. */
    accent: string
    /** Words a later version added or rewrote, at rest. */
    change: string
    /** Words a later version added or rewrote, hovered or active. */
    changeStrong: string
}

/** What the page tells the bridge: the passages to mark, and how. */
export interface MarksMessage {
    /** The protocol's tag. */
    channel: typeof CHANNEL
    /** What the message is. */
    type: 'marks'
    /** The passages. */
    marks: Mark[]
    /** The active thread's id, or null. */
    active: string | null
    /** The hovered thread's id, or null. */
    hover: string | null
    /** The colors to mark them in. */
    colors: Colors
}

/** What the page tells the bridge. */
export type ToBridge = MarksMessage | { channel: typeof CHANNEL; type: 'clear-selection' }

/** Where a passage is in the frame's document, in CSS pixels from its top. */
export interface Place {
    /** Its first line's top. */
    top: number
    /** Its last line's bottom. */
    bottom: number
}

/** What the reader selected: the passage it quotes, and where it is. */
export interface Selected {
    /** The passage, or null when it is longer than an anchor may be. */
    anchor: Anchor | null
    /** Its first line's top, from the frame document's top. */
    top: number
    /** Its last line's bottom, from the frame document's top. */
    bottom: number
    /** Its left edge, from the frame's left. */
    left: number
    /** Its right edge, from the frame's left. */
    right: number
}

/** What the bridge tells the page. */
export type FromBridge =
    | { channel: typeof CHANNEL; type: 'ready' }
    | { channel: typeof CHANNEL; type: 'layout'; height: number; places: Record<string, Place> }
    | { channel: typeof CHANNEL; type: 'selection'; selected: Selected | null }
    | { channel: typeof CHANNEL; type: 'click'; id: string | null }
    | { channel: typeof CHANNEL; type: 'hover'; id: string | null }
    | { channel: typeof CHANNEL; type: 'key'; key: Key }

/** The keys the page acts on, sent on while the frame has the focus. */
export type Key = 'j' | 'k' | 'c' | 'Escape'

/** The keys the bridge sends on. */
export const KEYS: readonly Key[] = ['j', 'k', 'c', 'Escape']

/** Read a message as one from the bridge, or null when it is not one. */
export function fromBridge(data: unknown): FromBridge | null {
    if (typeof data !== 'object' || data === null || !('channel' in data) || data.channel !== CHANNEL) {
        return null
    }
    const message = data as Record<string, unknown>
    switch (message['type']) {
        case 'ready': {
            return { channel: CHANNEL, type: 'ready' }
        }
        case 'layout': {
            const { height, places } = message
            if (!finite(height) || typeof places !== 'object' || places === null) {
                return null
            }
            const read: Record<string, Place> = {}
            for (const [id, place] of Object.entries(places)) {
                const found = placeOf(place)
                if (found) {
                    read[id] = found
                }
            }
            return { channel: CHANNEL, type: 'layout', height, places: read }
        }
        case 'selection': {
            return { channel: CHANNEL, type: 'selection', selected: selectedOf(message['selected']) }
        }
        case 'click':
        case 'hover': {
            const { id } = message
            return { channel: CHANNEL, type: message['type'], id: typeof id === 'string' ? id : null }
        }
        case 'key': {
            const key = KEYS.find((k) => k === message['key'])
            return key ? { channel: CHANNEL, type: 'key', key } : null
        }
        default: {
            return null
        }
    }
}

function finite(value: unknown): value is number {
    return typeof value === 'number' && Number.isFinite(value)
}

function placeOf(value: unknown): Place | null {
    if (typeof value !== 'object' || value === null) {
        return null
    }
    const { top, bottom } = value as Record<string, unknown>
    return finite(top) && finite(bottom) ? { top, bottom } : null
}

function selectedOf(value: unknown): Selected | null {
    if (typeof value !== 'object' || value === null) {
        return null
    }
    const { anchor, top, bottom, left, right } = value as Record<string, unknown>
    if (!finite(top) || !finite(bottom) || !finite(left) || !finite(right)) {
        return null
    }
    return { anchor: anchorOf(anchor), top, bottom, left, right }
}

function anchorOf(value: unknown): Anchor | null {
    if (typeof value !== 'object' || value === null) {
        return null
    }
    const { exact, prefix, suffix } = value as Record<string, unknown>
    if (typeof exact !== 'string' || !exact || typeof prefix !== 'string' || typeof suffix !== 'string') {
        return null
    }
    return { exact, prefix, suffix }
}
