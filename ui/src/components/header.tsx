import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { SignInLink } from '@/components/sign-in'
import { decisionsQuery, inboxQuery, sessionQuery, useSignIn } from '@/lib/api'
import { setTheme, useTheme } from '@/lib/theme'

/** What the header says about the page, beside the wordmark: where an artifact came from, say. */
export interface HeaderProps {
    /** Shown under the wordmark on wide screens, beside it on a phone. */
    provenance?: ReactNode
}

/**
 * Louvre's one-line header (ui/DESIGN.md, "Chrome"): the wordmark, what the page is, and the person's menu.
 */
export function Header({ provenance }: HeaderProps) {
    const { data: session } = useQuery(sessionQuery)
    const theme = useTheme()
    const { out } = useSignIn()
    const account = session?.account ?? null
    const news = useQuery({ ...inboxQuery, enabled: account !== null }).data?.entries.length ?? 0
    // How many open decisions ask the reader, who has not answered: Louvre's one call for their attention.
    // Read without polling: every page has the header, and an answer or a close reads it again by itself.
    const awaiting =
        useQuery({ ...decisionsQuery, enabled: account !== null, refetchInterval: false, staleTime: 60_000 }).data
            ?.awaiting ?? 0
    return (
        <header className="masthead">
            <div className="masthead-mark">
                <Link to="/" className="wordmark text-ink">
                    Louvre
                </Link>
                {provenance === undefined ? null : <p className="provenance">{provenance}</p>}
            </div>
            <nav className="masthead-nav" aria-label="Account">
                <button
                    type="button"
                    className="action"
                    onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                    aria-label={`Use the ${theme === 'dark' ? 'light' : 'dark'} theme`}
                >
                    {theme === 'dark' ? 'Light' : 'Dark'}
                </button>
                {account ? (
                    <>
                        <Link
                            to="/inbox"
                            className="action"
                            activeProps={{ className: 'action text-ink' }}
                            aria-label={news > 0 ? `Inbox, ${String(news)} new` : 'Inbox'}
                        >
                            Inbox{news > 0 ? <span className="news-count">{news}</span> : null}
                        </Link>
                        <Link
                            to="/decisions"
                            className="action"
                            activeProps={{ className: 'action text-ink' }}
                            aria-label={awaiting > 0 ? `Decisions, ${String(awaiting)} waiting on you` : 'Decisions'}
                        >
                            Decisions
                            {awaiting > 0 ? <span className="awaiting">{awaiting}</span> : null}
                        </Link>
                        {/* Minting a token is a desk task, so a phone's one line of chrome leaves it out. */}
                        <Link to="/tokens" className="action long" activeProps={{ className: 'action text-ink' }}>
                            Tokens
                        </Link>
                        <button type="button" className="action" onClick={() => out.mutate()} title={account.name}>
                            Sign out
                        </button>
                    </>
                ) : (
                    <SignInLink className="action action-primary">Sign in</SignInLink>
                )}
            </nav>
        </header>
    )
}
