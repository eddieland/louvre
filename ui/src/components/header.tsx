import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { sessionQuery, useSignIn } from '@/lib/api'
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
                        <Link to="/tokens" className="action" activeProps={{ className: 'action text-ink' }}>
                            Tokens
                        </Link>
                        <button type="button" className="action" onClick={() => out.mutate()} title={account.name}>
                            Sign out
                        </button>
                    </>
                ) : (
                    <Link to="/sign-in" className="action action-primary">
                        Sign in
                    </Link>
                )}
            </nav>
        </header>
    )
}
