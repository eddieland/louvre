import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'

import { Header } from '@/components/header'
import { Notice } from '@/components/notice'
import { SignIn } from '@/components/sign-in'
import { Footer } from '@/components/site'
import { ApiError, inboxQuery, sessionQuery, useMarkRead } from '@/lib/api'
import type { InboxEntry, News } from '@/lib/api'
import { ago, count, provenance, roman } from '@/lib/format'
import { usePageTitle } from '@/lib/title'

/** A person's inbox: what is new to them on the artifacts they take part in (ui/DESIGN.md, "Inbox"). */
export const Route = createFileRoute('/inbox')({
    component: Inbox,
})

function Inbox() {
    const session = useQuery(sessionQuery)
    const account = session.data?.account ?? null
    const inbox = useQuery({ ...inboxQuery, enabled: account !== null })
    const { all } = useMarkRead()
    const entries = inbox.data?.entries ?? []
    usePageTitle(entries.length > 0 ? `Inbox (${String(entries.length)})` : 'Inbox')

    if (session.isPending) {
        return <Header />
    }
    if (!account) {
        return (
            <>
                <Header />
                <main>
                    <Notice title="Sign in to see what is new">
                        <SignIn />
                    </Notice>
                </main>
                <Footer />
            </>
        )
    }
    return (
        <>
            <Header />
            <main className="catalogue" aria-labelledby="inbox-title">
                <div className="inbox-head">
                    <h1 id="inbox-title" className="title">
                        Inbox
                    </h1>
                    {entries.length > 0 ? (
                        <button type="button" className="action" disabled={all.isPending} onClick={() => all.mutate()}>
                            Mark all read
                        </button>
                    ) : null}
                </div>
                {inbox.error ? (
                    <p className="mt-3 text-muted">
                        {inbox.error instanceof ApiError ? inbox.error.message : 'It did not load; try again.'}
                    </p>
                ) : null}
                {inbox.data && entries.length === 0 ? (
                    <p className="mt-3 max-w-prose text-muted">
                        Nothing new. Replies and new versions on the artifacts you comment on, and on those your agents
                        publish, come here.
                    </p>
                ) : null}
                {entries.length > 0 ? (
                    <ol className="mt-6 border-t border-rule">
                        {entries.map((entry) => (
                            <Entry key={entry.artifact.id} entry={entry} />
                        ))}
                    </ol>
                ) : null}
            </main>
            <Footer />
        </>
    )
}

function Entry({ entry }: { entry: InboxEntry }) {
    const { artifact, news } = entry
    const from = provenance(artifact.origin)
    const versioned = artifact.latest_version > (entry.read_version ?? 0)
    const newest = news[0]
    return (
        <li className="entry">
            <Link
                to="/a/$artifactId"
                params={{ artifactId: artifact.id }}
                search={newest ? { t: newest.thread_id } : {}}
                className="entry-link"
            >
                <span className="entry-title">{artifact.title}</span>
                <span className="entry-meta">
                    <span>{artifact.namespace}</span>
                    {from ? <span className="text-ink">{from}</span> : null}
                    {versioned ? (
                        <span className="text-ink">
                            {entry.read_version === null ? 'New to you' : `Version ${roman(artifact.latest_version)}`}
                        </span>
                    ) : null}
                    {entry.threads > 0 ? <span>{count(entry.threads, 'thread')}</span> : null}
                    <span>{ago(entry.at)}</span>
                </span>
                <span className="entry-open">{entry.unread > 0 ? `${String(entry.unread)} new` : 'new'}</span>
                {news.length > 0 ? (
                    <span className="news">
                        {news.map((item) => (
                            <NewsLine key={item.seq} news={item} />
                        ))}
                    </span>
                ) : null}
            </Link>
        </li>
    )
}

function NewsLine({ news }: { news: News }) {
    const { author } = news
    return (
        <span className="news-item">
            {news.passage === null ? null : <span className="news-quote">{news.passage}</span>}
            <span className="news-line">
                <span className="who">{author.display_name}</span>
                {author.kind === 'agent' ? (
                    <em className="agent-badge">
                        (Agent{author.on_behalf_of_name ? `, for ${author.on_behalf_of_name}` : ''})
                    </em>
                ) : null}{' '}
                {said(news)}
            </span>
        </span>
    )
}

/** What a change says, after its author's name. */
function said(news: News): string {
    switch (news.kind) {
        case 'comment_created': {
            return news.body ?? 'wrote a comment, since deleted.'
        }
        case 'thread_resolved': {
            return 'resolved the thread.'
        }
        case 'thread_reopened': {
            return 'reopened the thread.'
        }
        default: {
            return news.kind satisfies never
        }
    }
}
