import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useEffect } from 'react'

import { Header } from '@/components/header'
import { Notice } from '@/components/notice'
import { SignIn } from '@/components/sign-in'
import { ApiError, decisionsQuery, sessionQuery } from '@/lib/api'
import type { Decision } from '@/lib/api'
import { waiting } from '@/lib/decisions'
import { ago } from '@/lib/format'

/** Every decision the reader reaches: those awaiting them, those open, those decided (ui/DESIGN.md, "Decisions"). */
export const Route = createFileRoute('/decisions')({
    component: DecisionsPage,
})

function DecisionsPage() {
    const session = useQuery(sessionQuery)
    const reachable = session.data?.configured === true && (session.data.account !== null || session.data.demo)
    const list = useQuery({ ...decisionsQuery, enabled: reachable })
    const me = session.data?.account?.login
    useEffect(() => {
        document.title = 'Decisions · Louvre'
    }, [])
    if (session.isPending) {
        return <Header />
    }
    if (!reachable) {
        return (
            <>
                <Header />
                <main>
                    <Notice title="Sign in to see decisions">
                        <SignIn />
                    </Notice>
                </main>
            </>
        )
    }
    const all = list.data?.decisions ?? []
    const groups = [
        { id: 'awaiting', title: 'Waiting on you', decisions: all.filter((d) => d.awaits_me) },
        { id: 'open', title: 'Open', decisions: all.filter((d) => d.state === 'open' && !d.awaits_me) },
        { id: 'decided', title: 'Decided', decisions: all.filter((d) => d.state === 'closed') },
    ]
    return (
        <>
            <Header />
            <main className="catalogue">
                <h1 className="title">Decisions</h1>
                <p className="mt-3 max-w-prose text-muted">
                    Questions agents and people asked on artifacts, to answer by choosing. Whoever asked reads the
                    answers back.
                </p>
                {list.error ? (
                    <p className="mt-6 text-accent">
                        {list.error instanceof ApiError ? list.error.message : 'The list did not load.'}
                    </p>
                ) : null}
                {list.data && all.length === 0 ? <p className="mt-6 text-muted">Nothing has been asked yet.</p> : null}
                {groups.map((group) =>
                    group.decisions.length > 0 ? (
                        <section key={group.id} className="mt-10" aria-labelledby={`decisions-${group.id}`}>
                            <h2 id={`decisions-${group.id}`} className="heading">
                                {group.title}
                            </h2>
                            <ol className="mt-3 border-t border-rule">
                                {group.decisions.map((d) => (
                                    <Entry key={d.id} decision={d} me={me} />
                                ))}
                            </ol>
                        </section>
                    ) : null,
                )}
            </main>
        </>
    )
}

function Entry({ decision, me }: { decision: Decision; me: string | undefined }) {
    const outcome = decision.options.find((o) => o.id === decision.outcome)
    const closed = decision.state === 'closed'
    return (
        <li className="entry">
            <Link
                to="/a/$artifactId"
                params={{ artifactId: decision.artifact_id }}
                search={{ decision: decision.id }}
                className="entry-link"
            >
                <span className="entry-title">{decision.question}</span>
                <span className="entry-meta">
                    <span className="text-ink">{decision.artifact_title}</span>
                    <span>{decision.author.display_name}</span>
                    <span>{ago(closed && decision.closed_at ? decision.closed_at : decision.created_at)}</span>
                    {outcome ? <span>Decided on {outcome.label}</span> : null}
                    <span>{waiting(decision, me)}</span>
                </span>
                {closed ? (
                    <span className="entry-open text-muted">Decided</span>
                ) : decision.awaits_me ? (
                    <span className="entry-open">Answer</span>
                ) : decision.mine ? (
                    <span className="entry-open text-muted">Answered</span>
                ) : (
                    <span className="entry-open text-muted">&mdash;</span>
                )}
            </Link>
        </li>
    )
}
