import { useEffect, useEffectEvent, useRef, useState } from 'react'
import type { RefObject } from 'react'

import { CHANNEL, fromBridge } from '@/bridge/protocol'
import type { Colors, FromBridge, Mark, ToBridge } from '@/bridge/protocol'
import type { Theme } from '@/lib/theme'

/** The frame's least height before the bridge reports the page's, in pixels. */
const FIRST_HEIGHT = 480
/** The most the frame grows to, in pixels: a page taller than this scrolls inside it. */
const MOST_HEIGHT = 60_000
/** The sandbox: scripts, and links that open a tab of their own; never the same origin as Louvre (REQUIREMENTS L7). */
export const SANDBOX = 'allow-scripts allow-popups allow-popups-to-escape-sandbox'

/** The frame an artifact's version is shown in, and what passes between it and the page. */
export interface FrameProps {
    /** The version's page, from the server's sandboxed route. */
    src: string
    /** What the frame shows, for the reader's assistive technology. */
    title: string
    /** The passages to mark. */
    marks: Mark[]
    /** The active thread's id, or null. */
    active: string | null
    /** The hovered thread's id, or null. */
    hover: string | null
    /** The theme the passages are colored in, and the artifact is shown in where it follows the reader's. */
    theme: Theme
    /** Where the page keeps the frame's element, to measure it. */
    frameRef: RefObject<HTMLIFrameElement | null>
    /** What the bridge said: where passages are, what was selected, clicked, hovered, or keyed. */
    onMessage: (message: FromBridge) => void
}

/**
 * An artifact in its sandboxed frame, as tall as its page, with the bridge inside it told what to mark. A frame shows
 * one page: give it a `key` of its `src`, so another version's page starts a frame of its own.
 */
export function Frame({ src, title, marks, active, hover, theme, frameRef, onMessage }: FrameProps) {
    const [height, setHeight] = useState(FIRST_HEIGHT)
    const ready = useRef(false)

    const sendMarks = useEffectEvent(() => {
        post(frameRef.current, { channel: CHANNEL, type: 'marks', marks, active, hover, colors: colorsOf() })
    })

    const handle = useEffectEvent((event: MessageEvent) => {
        if (!frameRef.current || event.source !== frameRef.current.contentWindow) {
            return
        }
        const message = fromBridge(event.data)
        if (!message) {
            return
        }
        if (message.type === 'ready') {
            ready.current = true
            sendMarks()
        } else if (message.type === 'layout') {
            setHeight(Math.min(Math.max(message.height, 120), MOST_HEIGHT))
        }
        onMessage(message)
    })

    useEffect(() => {
        const listener = (event: MessageEvent) => handle(event)
        globalThis.addEventListener('message', listener)
        return () => globalThis.removeEventListener('message', listener)
    }, [])

    useEffect(() => {
        if (ready.current) {
            post(frameRef.current, { channel: CHANNEL, type: 'marks', marks, active, hover, colors: colorsOf() })
        }
        // oxlint-disable-next-line react/exhaustive-effect-dependencies -- a theme changes the tokens colorsOf reads
    }, [frameRef, marks, active, hover, theme])

    return (
        <iframe
            ref={frameRef}
            className="exhibit"
            src={src}
            title={title}
            sandbox={SANDBOX}
            referrerPolicy="no-referrer"
            style={{ height: `${height}px`, colorScheme: theme }}
        />
    )
}

function post(frame: HTMLIFrameElement | null, message: ToBridge): void {
    frame?.contentWindow?.postMessage(message, '*')
}

/** The theme's tokens, as the bridge colors passages in them, read from the page. */
function colorsOf(): Colors {
    const style = getComputedStyle(document.documentElement)
    const token = (name: string) => style.getPropertyValue(`--${name}`).trim()
    return {
        rest: token('hl'),
        strong: token('hl-strong'),
        resolved: token('rule'),
        accent: token('accent'),
        change: token('chg'),
        changeStrong: token('chg-strong'),
    }
}
