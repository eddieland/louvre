import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { Notice } from '@/components/notice'
import { ApiError, boardsQuery, inboxQuery, listArtifacts, sessionQuery } from '@/lib/api'
import type { Listed, ListedBoard } from '@/lib/api'
import { ago, count, provenance } from '@/lib/format'

/** What a catalogue lists, and what it says around the list. */
export interface CatalogueProps {
    /** The one namespace to list, or every one the reader reaches but the demo's. */
    namespace?: string
    /** The list's title. */
    title: string
    /** Said above the boards and the list, such as what the demo is. */
    intro?: ReactNode
    /** Shown instead of the list when it holds nothing. */
    empty: ReactNode
    /** Said under the list. */
    after?: ReactNode
}

/** A list of artifacts, newest first, under the boards there are (ui/DESIGN.md, "Catalogue"). */
export function Catalogue({ namespace, title, intro, empty, after }: CatalogueProps) {
    const list = useInfiniteQuery({
        queryKey: ['artifacts', namespace ?? null],
        queryFn: ({ pageParam }) => listArtifacts(pageParam, namespace),
        initialPageParam: null as string | null,
        getNextPageParam: (last) => last.next_cursor,
    })
    const artifacts = list.data?.pages.flatMap((page) => page.artifacts) ?? []
    const boards = useQuery(boardsQuery(namespace)).data?.boards ?? []
    // The artifacts with news for a signed-in reader (their inbox), marked in the list.
    const signedIn = Boolean(useQuery(sessionQuery).data?.account)
    const inbox = useQuery({ ...inboxQuery, enabled: signedIn }).data?.entries ?? []
    const news = new Set(inbox.map((entry) => entry.artifact.id))
    if (list.error) {
        return (
            <Notice title="The list did not load">
                <p>{list.error instanceof ApiError ? list.error.message : 'Try again in a moment.'}</p>
            </Notice>
        )
    }
    if (list.isPending) {
        return null
    }
    if (artifacts.length === 0 && boards.length === 0) {
        return empty
    }
    return (
        <section className="catalogue" aria-labelledby="catalogue-title">
            {intro === undefined ? null : <div className="mb-6 max-w-prose font-ui text-sm text-muted">{intro}</div>}
            {boards.length > 0 ? (
                <section className="mb-12" aria-labelledby="boards-title">
                    <h2 id="boards-title" className="title">
                        Boards
                    </h2>
                    <ol className="mt-6 border-t border-rule">
                        {boards.map((board) => (
                            <BoardEntry key={board.id} board={board} />
                        ))}
                    </ol>
                </section>
            ) : null}
            <h1 id="catalogue-title" className="title">
                {title}
            </h1>
            <ol className="mt-6 border-t border-rule">
                {artifacts.map((artifact) => (
                    <Entry key={artifact.id} artifact={artifact} news={news.has(artifact.id)} />
                ))}
            </ol>
            {list.hasNextPage ? (
                <button
                    type="button"
                    className="action mt-6"
                    onClick={() => void list.fetchNextPage()}
                    disabled={list.isFetchingNextPage}
                >
                    Older
                </button>
            ) : null}
            {after === undefined ? null : <div className="mt-12 max-w-prose font-ui text-sm text-muted">{after}</div>}
        </section>
    )
}

/** What a page says in place of its list when the deployment has no database. */
export function NeedsDatabase() {
    return (
        <Notice title="Louvre needs its database">
            <p>
                This deployment has no Postgres database yet. Set DATABASE_URL (or connect a Postgres store in Vercel,
                which sets POSTGRES_URL), then reload: Louvre makes its tables itself.
            </p>
            <p>docs/DEPLOY.md has every step.</p>
        </Notice>
    )
}

function Entry({ artifact, news }: { artifact: Listed; news: boolean }) {
    const from = provenance(artifact.origin)
    return (
        <li className="entry">
            <Link to="/a/$artifactId" params={{ artifactId: artifact.id }} className="entry-link">
                <span className="entry-title">{artifact.title}</span>
                <span className="entry-meta">
                    {news ? <span className="text-accent">New to you</span> : null}
                    <span>{artifact.namespace}</span>
                    {from ? <span className="text-ink">{from}</span> : null}
                    <span>{ago(artifact.updated_at)}</span>
                    {artifact.latest_version > 1 ? <span>{count(artifact.latest_version, 'version')}</span> : null}
                    {artifact.awaiting > 0 ? (
                        <span className="text-accent">Your answer is wanted</span>
                    ) : artifact.open_decisions > 0 ? (
                        <span>{count(artifact.open_decisions, 'open decision')}</span>
                    ) : null}
                </span>
                {artifact.open_threads > 0 ? (
                    <span className="entry-open">{artifact.open_threads} open</span>
                ) : (
                    <span className="entry-open text-muted">&mdash;</span>
                )}
            </Link>
        </li>
    )
}

function BoardEntry({ board }: { board: ListedBoard }) {
    return (
        <li className="entry">
            <Link to="/b/$boardId" params={{ boardId: board.id }} className="entry-link">
                <span className="entry-title">{board.title}</span>
                <span className="entry-meta">
                    <span>{board.namespace}</span>
                    <span className="text-ink">{count(board.frames, 'frame')}</span>
                </span>
                {board.open_threads > 0 ? (
                    <span className="entry-open">{board.open_threads} open</span>
                ) : (
                    <span className="entry-open text-muted">&mdash;</span>
                )}
            </Link>
        </li>
    )
}
