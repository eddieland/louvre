import { Link } from '@tanstack/react-router'
import { useEffect, useEffectEvent, useRef, useState } from 'react'
import type { CSSProperties, PointerEvent as ReactPointerEvent } from 'react'

import { SANDBOX } from '@/components/frame'
import { Header } from '@/components/header'
import { bounds, fit, live, panBy, wheelFactor, ZOOM_STEP, zoomAt } from '@/lib/canvas'
import type { Point, View } from '@/lib/canvas'
import { count } from '@/lib/format'
import { useTheme } from '@/lib/theme'
import type { Theme } from '@/lib/theme'

/** Room above each frame for its label, in canvas pixels, so fitting the board keeps the top row's labels in view. */
const LABEL_ROOM = 80
/** Room around the board when it is fitted to the screen, in screen pixels. */
const PADDING = 24
/** How far a press moves, in screen pixels, before it is a drag rather than a tap on a frame. */
const DRAG = 4
/** How far an arrow key moves the canvas, in screen pixels. */
const PAN_STEP = 80
/** How long the zoom is still before the frames' pages are drawn again, in milliseconds. */
const SETTLE = 200

/** One page on a board's canvas, at a screen's size and a place, in CSS pixels. */
export interface CanvasFrame {
    /** Unique on its board. */
    id: string
    /** What the page is called. */
    title: string
    /** What the board calls the frame beside the title, such as "Phone, 390". */
    label: string
    /** Its left edge on the canvas. */
    x: number
    /** Its top edge on the canvas. */
    y: number
    /** The width it is shown at, as a screen that wide would show it. */
    width: number
    /** The height it is shown at. */
    height: number
    /** The page it shows, framed sandboxed. */
    src: string
    /** How many threads are open on it. */
    openThreads: number
    /** Where opening it goes: an artifact's page, with the way back to its board, or a page of the server's own. */
    opens: { artifactId: string; boardId: string } | { href: string }
}

/** What a board's page shows. */
export interface BoardCanvasProps {
    /** The board's title. */
    title: string
    /** Where it is from, shown before its title in the header on wide screens. */
    namespace: string
    /** What the reader can do here, in the toolbar on wide screens. */
    hint: string
    /** Its frames. */
    frames: CanvasFrame[]
}

/**
 * A board on its page (ui/DESIGN.md, "Boards"): the header, the toolbar with its zoom control, and the canvas of
 * frames, fitted to the screen, to pan and zoom by pointer, touch, and keys.
 */
export function BoardCanvas({ title, namespace, hint, frames }: BoardCanvasProps) {
    const theme = useTheme()
    const viewportRef = useRef<HTMLDivElement>(null)
    const [view, setView] = useState<View | null>(null)
    // Whether the view is still the fit, so a resized screen fits the board again.
    const fitted = useRef(true)
    // The pointers down on the canvas, where each last was; and where the first went down, until it drags.
    const pointers = useRef(new Map<number, Point>())
    const pressedAt = useRef<Point | null>(null)
    const dragged = useRef(false)
    // The moves made since the board was last drawn: a phone sends pointer moves faster than its screen redraws, so
    // they are drawn together, once a frame.
    const pending = useRef<((current: View) => View) | null>(null)
    // The view once it has been still for a moment, and the canvas's size: the pages are drawn from them, not from the
    // view. Each step of a zoom would redraw every page at the new size, and each step of a pan on a phone load and
    // unload them, which a phone has not the memory to do many times a second.
    const [settled, setSettled] = useState<View | null>(null)
    const [screen, setScreen] = useState<{ width: number; height: number } | null>(null)

    const world = bounds(frames, LABEL_ROOM)
    // While the zoom changes, the pages are put away; once it is still, those the screen can hold are drawn.
    const zooming = view !== null && settled?.scale !== view.scale
    const shown = new Set(settled && screen ? live(frames, settled, screen.width, screen.height).map((f) => f.id) : [])

    const fitView = () => {
        const viewport = viewportRef.current
        if (viewport) {
            fitted.current = true
            pending.current = null
            setView(fit(world, viewport.clientWidth, viewport.clientHeight, PADDING))
        }
    }

    const change = (next: (current: View) => View) => {
        fitted.current = false
        const before = pending.current
        pending.current = before ? (current) => next(before(current)) : next
        if (!before) {
            requestAnimationFrame(() => {
                const moves = pending.current
                pending.current = null
                if (moves) {
                    setView((was) => (was ? moves(was) : was))
                }
            })
        }
    }

    const middle = (): Point => {
        const viewport = viewportRef.current
        return { x: (viewport?.clientWidth ?? 0) / 2, y: (viewport?.clientHeight ?? 0) / 2 }
    }

    const zoomBy = (factor: number) => change((was) => zoomAt(was, factor, middle()))

    useEffect(() => {
        const timer = setTimeout(() => setSettled(view), SETTLE)
        return () => clearTimeout(timer)
    }, [view])

    const onResize = useEffectEvent(() => {
        const viewport = viewportRef.current
        if (viewport) {
            setScreen({ width: viewport.clientWidth, height: viewport.clientHeight })
        }
        if (fitted.current) {
            fitView()
        }
    })
    useEffect(() => {
        const viewport = viewportRef.current
        if (!viewport) {
            return
        }
        // It reports the viewport's size once when it starts, which fits the board the first time.
        const observer = new ResizeObserver(() => onResize())
        observer.observe(viewport)
        return () => observer.disconnect()
    }, [])

    // The wheel zooms about the cursor. It is listened to by hand, not as a prop, so it can keep the page still.
    const onWheel = useEffectEvent((event: WheelEvent) => {
        event.preventDefault()
        const at = viewportRef.current?.getBoundingClientRect()
        if (at) {
            const factor = wheelFactor(event.deltaY, event.deltaMode, event.ctrlKey)
            change((was) => zoomAt(was, factor, { x: event.clientX - at.left, y: event.clientY - at.top }))
        }
    })
    useEffect(() => {
        const viewport = viewportRef.current
        const listener = (event: WheelEvent) => onWheel(event)
        viewport?.addEventListener('wheel', listener, { passive: false })
        return () => viewport?.removeEventListener('wheel', listener)
    }, [])

    const onWindowKey = useEffectEvent((event: KeyboardEvent) => {
        const target = event.target instanceof Element ? event.target : null
        const typing = target !== null && target.closest('input, textarea, select') !== null
        if (typing || event.metaKey || event.ctrlKey || event.altKey) {
            return
        }
        const moves: Record<string, () => void> = {
            '+': () => zoomBy(ZOOM_STEP),
            '=': () => zoomBy(ZOOM_STEP),
            '-': () => zoomBy(1 / ZOOM_STEP),
            '0': fitView,
            ArrowLeft: () => change((was) => panBy(was, PAN_STEP, 0)),
            ArrowRight: () => change((was) => panBy(was, -PAN_STEP, 0)),
            ArrowUp: () => change((was) => panBy(was, 0, PAN_STEP)),
            ArrowDown: () => change((was) => panBy(was, 0, -PAN_STEP)),
        }
        const move = moves[event.key]
        if (move) {
            event.preventDefault()
            move()
        }
    })
    useEffect(() => {
        const listener = (event: KeyboardEvent) => onWindowKey(event)
        globalThis.addEventListener('keydown', listener)
        return () => globalThis.removeEventListener('keydown', listener)
    }, [])

    useEffect(() => {
        document.title = `${title} · Louvre`
    }, [title])

    const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
        if (event.button !== 0) {
            return
        }
        const at = pointOf(event)
        pointers.current.set(event.pointerId, at)
        if (pointers.current.size === 1) {
            pressedAt.current = at
            dragged.current = false
        }
    }

    const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
        const was = pointers.current.get(event.pointerId)
        if (!was) {
            return
        }
        const now = pointOf(event)
        const other = [...pointers.current].find(([id]) => id !== event.pointerId)?.[1]
        if (other) {
            // A pinch: zoom by how far the two have spread, about their middle, and pan as the middle moves.
            pointers.current.set(event.pointerId, now)
            dragged.current = true
            const before = { at: halfway(was, other), apart: distance(was, other) }
            const after = { at: halfway(now, other), apart: distance(now, other) }
            const factor = before.apart > 0 ? after.apart / before.apart : 1
            change((current) =>
                zoomAt(panBy(current, after.at.x - before.at.x, after.at.y - before.at.y), factor, after.at),
            )
            return
        }
        const from = pressedAt.current
        if (!dragged.current && from && distance(from, now) < DRAG) {
            return
        }
        if (!dragged.current) {
            // A drag: the canvas takes the pointer, so it keeps the drag when the pointer leaves it.
            dragged.current = true
            event.currentTarget.setPointerCapture(event.pointerId)
        }
        pointers.current.set(event.pointerId, now)
        change((current) => panBy(current, now.x - was.x, now.y - was.y))
    }

    const onPointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
        pointers.current.delete(event.pointerId)
    }

    return (
        <div className="board-page">
            <Header
                provenance={
                    <>
                        <span className="long">{namespace} &middot; </span>
                        <b>{title}</b>
                    </>
                }
            />
            <nav className="toolbar" aria-label="Board">
                <p className="board-hint">
                    <span className="tabular-nums">{count(frames.length, 'frame')}</span>
                    <span className="long">{hint}</span>
                </p>
                <fieldset className="zoom">
                    <legend className="sr-only">Zoom</legend>
                    <button type="button" className="pill" aria-label="Zoom out" onClick={() => zoomBy(1 / ZOOM_STEP)}>
                        &minus;
                    </button>
                    <output className="zoom-level" aria-label="Zoom level">
                        {view ? `${String(Math.round(view.scale * 100))}%` : ''}
                    </output>
                    <button type="button" className="pill" aria-label="Zoom in" onClick={() => zoomBy(ZOOM_STEP)}>
                        +
                    </button>
                    <button type="button" className="pill" onClick={fitView} aria-label="Fit to screen">
                        Fit
                    </button>
                </fieldset>
            </nav>
            <div
                ref={viewportRef}
                className="canvas"
                onPointerDown={onPointerDown}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
                onPointerCancel={onPointerUp}
                onClickCapture={(event) => {
                    // A drag that ends on a frame does not open it.
                    if (dragged.current) {
                        event.preventDefault()
                        event.stopPropagation()
                    }
                }}
            >
                <div
                    className="world"
                    data-ready={view ? '' : undefined}
                    data-zooming={zooming ? '' : undefined}
                    style={view ? drawn(view) : { visibility: 'hidden' }}
                >
                    {frames.map((frame) => (
                        <FrameOnBoard key={frame.id} frame={frame} theme={theme} running={shown.has(frame.id)} />
                    ))}
                </div>
            </div>
        </div>
    )
}

/**
 * A frame on the canvas: its label above it, its page running inside while it is live, its sheet alone while it is
 * not, and a link over it that opens it.
 */
function FrameOnBoard({ frame, theme, running }: { frame: CanvasFrame; theme: Theme; running: boolean }) {
    const name = `${frame.title}, ${frame.label}`
    const label = <span className="sr-only">Open {name}</span>
    const { opens } = frame
    return (
        <figure
            className="board-frame"
            data-live={running ? '' : undefined}
            style={{ left: frame.x, top: frame.y, width: frame.width, height: frame.height }}
        >
            <figcaption className="board-label">
                <span className="text-ink">{frame.title}</span>
                <span>{frame.label}</span>
                {frame.openThreads > 0 ? <span className="text-accent">{String(frame.openThreads)} open</span> : null}
            </figcaption>
            {/* Inert: the board takes every pointer and key, so a frame is read by opening it. */}
            {running ? (
                <iframe
                    src={frame.src}
                    title={name}
                    sandbox={SANDBOX}
                    referrerPolicy="no-referrer"
                    inert
                    style={{ colorScheme: theme }}
                />
            ) : null}
            {'href' in opens ? (
                <a href={opens.href} className="board-open" draggable={false}>
                    {label}
                </a>
            ) : (
                <Link
                    to="/a/$artifactId"
                    params={{ artifactId: opens.artifactId }}
                    search={{ board: opens.boardId, frame: frame.id }}
                    className="board-open"
                    draggable={false}
                >
                    {label}
                </Link>
            )}
        </figure>
    )
}

/** The canvas drawn at a view, with the scale as `--zoom`, which keeps the frames' labels and outlines one size. */
function drawn(view: View): CSSProperties {
    const transform = `translate(${String(view.x)}px, ${String(view.y)}px) scale(${String(view.scale)})`
    return { transform, '--zoom': view.scale } as CSSProperties
}

/** Where a pointer is in the element its handler is on. */
function pointOf(event: ReactPointerEvent<HTMLElement>): Point {
    const at = event.currentTarget.getBoundingClientRect()
    return { x: event.clientX - at.left, y: event.clientY - at.top }
}

function halfway(a: Point, b: Point): Point {
    return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
}

function distance(a: Point, b: Point): number {
    return Math.hypot(a.x - b.x, a.y - b.y)
}
