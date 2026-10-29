import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { Notice } from '@/components/notice'
import { FoundLines, Marked, SearchField } from '@/components/search'
import { ApiError, boardsQuery, inboxQuery, listArtifacts, sessionQuery } from '@/lib/api'
import type { Listed, ListedBoard } from '@/lib/api'
import { ago, count, provenance } from '@/lib/format'

/** What a catalogue lists, and what it says around the list. */
export interface CatalogueProps {
    /** The one namespace to list, or every one the reader reaches but the demo's. */
    namespace?: string
    /** The origin pairs every artifact listed holds, such as its ticket; the list is titled by them, without boards. */
    origin?: Record<string, string>
    /** The words every artifact listed holds, in its title, its words, or its comments; the list has no boards. */
    query?: string
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
export function Catalogue({ namespace, origin, query, title, intro, empty, after }: CatalogueProps) {
    const list = useInfiniteQuery({
        queryKey: ['artifacts', namespace ?? null, origin ?? null, query ?? null],
        queryFn: ({ pageParam }) => listArtifacts(pageParam, namespace, origin, query),
        initialPageParam: null as string | null,
        getNextPageParam: (last) => last.next_cursor,
    })
    const artifacts = list.data?.pages.flatMap((page) => page.artifacts) ?? []
    // Boards are neither filtered by origin nor searched: a filtered or searched list is the artifacts alone.
    const whole = origin === undefined && query === undefined
    const listedBoards = useQuery({ ...boardsQuery(namespace), enabled: whole }).data?.boards ?? []
    // A query turned off still answers with what it fetched before, as the whole list did before a search.
    const boards = whole ? listedBoards : []
    // The artifacts with news for a signed-in reader (their inbox), marked in the list.
    const signedIn = Boolean(useQuery(sessionQuery).data?.account)
    const inbox = useQuery({ ...inboxQuery, enabled: signedIn }).data?.entries ?? []
    const news = new Set(inbox.map((entry) => entry.artifact.id))
    const from = origin === undefined ? null : provenance(origin)
    // What the list is filtered by, said under its title: the origin's pairs, then the words searched for.
    const filters = [
        ...Object.entries(origin ?? {}).map(([key, value]) => `${key} ${value}`),
        ...(query === undefined ? [] : [`holding “${query}”`]),
    ]
    const head = (
        <div className="catalogue-head">
            <h1 id="catalogue-title" className="title">
                {from === null ? title : `From ${from}`}
            </h1>
            <SearchField query={query} origin={origin} />
        </div>
    )
    if (list.error) {
        const said = list.error instanceof ApiError ? list.error.message : 'Try again in a moment.'
        // A search the server refused keeps its field, to search again.
        return query === undefined ? (
            <Notice title="The list did not load">
                <p>{said}</p>
            </Notice>
        ) : (
            <section className="catalogue" aria-labelledby="catalogue-title">
                {head}
                <p className="mt-3 max-w-prose text-muted">{said}</p>
            </section>
        )
    }
    if (list.isPending) {
        return null
    }
    if (query === undefined && from !== null && artifacts.length === 0) {
        return (
            <Notice title={`Nothing from ${from}`}>
                <p>No artifact you can read came from {from}.</p>
                <EveryArtifact />
            </Notice>
        )
    }
    if (whole && artifacts.length === 0 && boards.length === 0) {
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
            {head}
            {whole ? null : (
                <p className="mt-2 font-ui text-sm text-muted">
                    {filters.join(', ')} &middot; <EveryArtifact />
                </p>
            )}
            {query !== undefined && artifacts.length === 0 ? (
                <p className="mt-6 max-w-prose text-muted">
                    Nothing you can read holds these words in its title, its page, or its comments. A word is found
                    where a word starts: &ldquo;retr&rdquo; finds &ldquo;retry&rdquo;.
                </p>
            ) : (
                <ol className="mt-6 border-t border-rule">
                    {artifacts.map((artifact) => (
                        <Entry key={artifact.id} artifact={artifact} news={news.has(artifact.id)} />
                    ))}
                </ol>
            )}
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

/** The way back from a filtered list to the whole one, on the same page. */
function EveryArtifact() {
    return (
        <Link to="." search={{}} className="link">
            Every artifact
        </Link>
    )
}

function Entry({ artifact, news }: { artifact: Listed; news: boolean }) {
    const from = provenance(artifact.origin)
    const { found } = artifact
    // A search that found words in a comment opens the artifact at its thread, as the inbox opens its news.
    const thread = found?.comments[0]?.thread_id
    return (
        <li className="entry">
            <Link
                to="/a/$artifactId"
                params={{ artifactId: artifact.id }}
                search={thread === undefined ? {} : { t: thread }}
                className="entry-link"
            >
                <span className="entry-title">{found ? <Marked runs={found.title} /> : artifact.title}</span>
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
                {found ? <FoundLines found={found} /> : null}
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
