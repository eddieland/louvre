import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'

import { Header } from '@/components/header'
import { Notice } from '@/components/notice'
import { SignIn, SignInLink } from '@/components/sign-in'
import { ApiError, boardsQuery, listArtifacts, sessionQuery } from '@/lib/api'
import type { Listed, ListedBoard } from '@/lib/api'
import { ago, count, provenance } from '@/lib/format'

/** The catalogue: every artifact the reader reaches, newest first (ui/DESIGN.md, "Catalogue"). */
export const Route = createFileRoute('/')({
    component: Catalogue,
})

function Catalogue() {
    const session = useQuery(sessionQuery)
    const reachable = session.data?.configured === true && (session.data.account !== null || session.data.demo)
    const list = useInfiniteQuery({
        queryKey: ['artifacts'],
        queryFn: ({ pageParam }) => listArtifacts(pageParam),
        initialPageParam: null as string | null,
        getNextPageParam: (last) => last.next_cursor,
        enabled: reachable,
    })
    const artifacts = list.data?.pages.flatMap((page) => page.artifacts) ?? []
    const boards = useQuery({ ...boardsQuery, enabled: reachable }).data?.boards ?? []
    return (
        <>
            <Header />
            <main>{body()}</main>
        </>
    )

    function body() {
        if (session.isPending) {
            return null
        }
        if (session.data?.configured === false) {
            return (
                <Notice title="Louvre needs its database">
                    <p>
                        This deployment has no Postgres database yet. Set DATABASE_URL (or connect a Postgres store in
                        Vercel, which sets POSTGRES_URL), then reload: Louvre makes its tables itself.
                    </p>
                    <p>docs/DEPLOY.md has every step.</p>
                </Notice>
            )
        }
        if (!reachable) {
            return (
                <Notice title="Sign in to read">
                    <p>Louvre holds the pages agents publish for people to read and comment on.</p>
                    <SignIn />
                </Notice>
            )
        }
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
        if (artifacts.length === 0) {
            return (
                <Notice title="Nothing published yet">
                    <p>
                        Agents publish here through Louvre&rsquo;s MCP server. Mint a token for one on the{' '}
                        <Link to="/tokens" className="link">
                            Tokens
                        </Link>{' '}
                        page, and what it publishes appears here.
                    </p>
                </Notice>
            )
        }
        return (
            <section className="catalogue" aria-labelledby="catalogue-title">
                {session.data?.account === null ? (
                    <p className="mb-6 font-ui text-sm text-muted">
                        You are reading the demo. <SignInLink className="link">Sign in</SignInLink> to comment.
                    </p>
                ) : null}
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
                    Artifacts
                </h1>
                <ol className="mt-6 border-t border-rule">
                    {artifacts.map((artifact) => (
                        <Entry key={artifact.id} artifact={artifact} />
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
            </section>
        )
    }
}

function Entry({ artifact }: { artifact: Listed }) {
    const from = provenance(artifact.origin)
    return (
        <li className="entry">
            <Link to="/a/$artifactId" params={{ artifactId: artifact.id }} className="entry-link">
                <span className="entry-title">{artifact.title}</span>
                <span className="entry-meta">
                    <span>{artifact.namespace}</span>
                    {from ? <span className="text-ink">{from}</span> : null}
                    <span>{ago(artifact.updated_at)}</span>
                    {artifact.latest_version > 1 ? <span>{count(artifact.latest_version, 'version')}</span> : null}
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
