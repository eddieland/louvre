import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'

import { BoardCanvas } from '@/components/board'
import type { CanvasFrame } from '@/components/board'
import { Header } from '@/components/header'
import { Notice } from '@/components/notice'
import { ApiError, boardQuery } from '@/lib/api'
import type { BoardFrame } from '@/lib/api'

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
    const { title, namespace } = board.data.board
    return (
        <BoardCanvas
            key={boardId}
            title={title}
            namespace={namespace}
            hint="Drag to move, scroll or pinch to zoom, and open a frame to read it and comment."
            frames={board.data.frames.map((frame) => onCanvas(boardId, frame))}
        />
    )
}

/** A frame of a stored board, on the canvas: its artifact's latest version, opened on the artifact's page. */
function onCanvas(boardId: string, frame: BoardFrame): CanvasFrame {
    const { artifact } = frame
    return {
        ...frame,
        title: artifact.title,
        src: `/content/${encodeURIComponent(artifact.id)}/${String(artifact.latest_version)}`,
        openThreads: artifact.open_threads,
        opens: { artifactId: artifact.id, boardId },
    }
}
