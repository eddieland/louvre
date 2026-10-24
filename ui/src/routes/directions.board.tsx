import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'

import { BoardCanvas } from '@/components/board'
import type { CanvasFrame } from '@/components/board'
import { Header } from '@/components/header'
import { Notice } from '@/components/notice'
import { directionsBoardQuery } from '@/lib/api'
import type { DirectionsFrame } from '@/lib/api'

/**
 * The design study as a board, from the repository's pages alone: it needs no database and no demo, so every
 * deployment shows it. Each frame opens the direction's own page, as /directions serves it; nothing here is stored,
 * so nothing takes a comment.
 */
export const Route = createFileRoute('/directions/board')({
    component: DirectionsBoard,
})

function DirectionsBoard() {
    const board = useQuery(directionsBoardQuery)
    if (board.error) {
        return (
            <>
                <Header />
                <Notice title="It did not load">
                    <p>{board.error.message}</p>
                </Notice>
            </>
        )
    }
    if (!board.data) {
        return <Header />
    }
    return (
        <BoardCanvas
            title={board.data.board.title}
            namespace={board.data.board.namespace}
            hint="Drag to move, scroll or pinch to zoom, and open a frame to try its direction."
            frames={board.data.frames.map(onCanvas)}
        />
    )
}

/** A direction's page on the canvas, opened as the design study serves it. */
function onCanvas(frame: DirectionsFrame): CanvasFrame {
    const { id, title, label, x, y, width, height, src } = frame
    return { id, title, label, x, y, width, height, src, openThreads: 0, opens: { href: src } }
}
