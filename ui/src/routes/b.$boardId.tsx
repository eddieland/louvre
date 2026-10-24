import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useEffect, useEffectEvent, useRef, useState } from 'react'
import type { CSSProperties, PointerEvent as ReactPointerEvent } from 'react'

import { SANDBOX } from '@/components/frame'
import { Header } from '@/components/header'
import { Notice } from '@/components/notice'
import { ApiError, boardQuery } from '@/lib/api'
import type { Board, BoardFrame } from '@/lib/api'
import { bounds, fit, panBy, wheelFactor, ZOOM_STEP, zoomAt } from '@/lib/canvas'
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

/** A board's page: its frames on a canvas to pan and zoom, each opened to read whole (ui/DESIGN.md, "Boards"). */
export const Route = createFileRoute('/b/$boardId')({
    component: BoardPage,
})

function BoardPage() {
    const { boardId } = Route.useParams()
    const board = useQuery(boardQuery(boardId))
    if (board.error) {
        const missing = board.error instanceof ApiError && board.error.status === 404
        const signIn = board.error instanceof ApiError && board.error.status === 401
        return (
            <>
                <Header />
                <Notice title={missing ? 'No such board' : signIn ? 'Sign in to see this' : 'It did not load'}>
                    <p>{missing ? 'The link may be mistyped.' : board.error.message}</p>
                    {signIn ? (
                        <Link to="/sign-in" className="link">
                            Sign in
                        </Link>
                    ) : (
                        <Link to="/" className="link">
                            Every artifact
                        </Link>
                    )}
                </Notice>
            </>
        )
    }
    if (!board.data) {
        return <Header />
    }
    return <Canvas key={boardId} board={board.data} />
}

function Canvas({ board }: { board: Board }) {
    const theme = useTheme()
    const viewportRef = useRef<HTMLDivElement>(null)
    const [view, setView] = useState<View | null>(null)
    // Whether the view is still the fit, so a resized screen fits the board again.
    const fitted = useRef(true)
    // The pointers down on the canvas, where each last was; and where the first went down, until it drags.
    const pointers = useRef(new Map<number, Point>())
    const pressedAt = useRef<Point | null>(null)
    const dragged = useRef(false)

    const world = bounds(board.frames, LABEL_ROOM)

    const fitView = () => {
        const viewport = viewportRef.current
        if (viewport) {
            fitted.current = true
            setView(fit(world, viewport.clientWidth, viewport.clientHeight, PADDING))
        }
    }

    const change = (next: (current: View) => View) => {
        fitted.current = false
        setView((was) => (was ? next(was) : was))
    }

    const middle = (): Point => {
        const viewport = viewportRef.current
        return { x: (viewport?.clientWidth ?? 0) / 2, y: (viewport?.clientHeight ?? 0) / 2 }
    }

    const zoomBy = (factor: number) => change((was) => zoomAt(was, factor, middle()))

    const onResize = useEffectEvent(() => {
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
        document.title = `${board.board.title} · Louvre`
    }, [board.board.title])

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
                        <span className="long">{board.board.namespace} &middot; </span>
                        <b>{board.board.title}</b>
                    </>
                }
            />
            <nav className="toolbar" aria-label="Board">
                <p className="board-hint">
                    <span className="tabular-nums">{count(board.frames.length, 'frame')}</span>
                    <span className="long">
                        Drag to move, scroll or pinch to zoom, and open a frame to read it and comment.
                    </span>
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
                    style={view ? drawn(view) : { visibility: 'hidden' }}
                >
                    {board.frames.map((frame) => (
                        <FrameOnBoard key={frame.id} boardId={board.board.id} frame={frame} theme={theme} />
                    ))}
                </div>
            </div>
        </div>
    )
}

/** A frame on the canvas: its label above it, its artifact running inside, and a link over it that opens it. */
function FrameOnBoard({ boardId, frame, theme }: { boardId: string; frame: BoardFrame; theme: Theme }) {
    const { artifact } = frame
    const name = `${artifact.title}, ${frame.label}`
    return (
        <figure
            className="board-frame"
            style={{ left: frame.x, top: frame.y, width: frame.width, height: frame.height }}
        >
            <figcaption className="board-label">
                <span className="text-ink">{artifact.title}</span>
                <span>{frame.label}</span>
                {artifact.open_threads > 0 ? (
                    <span className="text-accent">{String(artifact.open_threads)} open</span>
                ) : null}
            </figcaption>
            {/* Inert: the board takes every pointer and key, so a frame is read by opening it. */}
            <iframe
                src={`/content/${encodeURIComponent(artifact.id)}/${String(artifact.latest_version)}`}
                title={name}
                sandbox={SANDBOX}
                referrerPolicy="no-referrer"
                inert
                style={{ colorScheme: theme }}
            />
            <Link
                to="/a/$artifactId"
                params={{ artifactId: artifact.id }}
                search={{ board: boardId, frame: frame.id }}
                className="board-open"
                draggable={false}
            >
                <span className="sr-only">Open {name}</span>
            </Link>
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
