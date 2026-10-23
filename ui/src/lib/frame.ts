// What the artifact page tells its frame outside the Frame component's own messages.

import { CHANNEL } from '@/bridge/protocol'
import type { ToBridge } from '@/bridge/protocol'

/** Clear the reader's selection inside the frame, once their comment has a thread of its own. */
export function clearSelection(frame: HTMLIFrameElement | null): void {
    const message: ToBridge = { channel: CHANNEL, type: 'clear-selection' }
    frame?.contentWindow?.postMessage(message, '*')
}
