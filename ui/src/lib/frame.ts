// What the artifact page tells its frame outside the Frame component's own messages.

import { CHANNEL } from '@/bridge/protocol'
import type { ToBridge } from '@/bridge/protocol'

/** Clear the reader's selection inside the frame, once their comment has a thread of its own. */
export function clearSelection(frame: HTMLIFrameElement | null): void {
    const message: ToBridge = { channel: CHANNEL, type: 'clear-selection' }
    frame?.contentWindow?.postMessage(message, '*')
}

/** Ask the frame's map to pan and zoom to a mark's place: a decision's option's, a change's, or a draft's. */
export function showPlace(frame: HTMLIFrameElement | null, id: string): void {
    const message: ToBridge = { channel: CHANNEL, type: 'show', id }
    frame?.contentWindow?.postMessage(message, '*')
}
