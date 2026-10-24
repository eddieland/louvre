import { useQuery } from '@tanstack/react-query'
import { Link, useLocation, useNavigate } from '@tanstack/react-router'
import type { ReactNode } from 'react'
import { useState } from 'react'

import { sessionQuery, useSignIn } from '@/lib/api'
import { localPath } from '@/lib/paths'

/** Why a sign-in came back unfinished, as the server says it in ?sign_in=. */
const WHY: Record<string, string> = {
    cancelled: 'You did not approve Louvre on GitHub, so you are not signed in.',
    denied: 'That GitHub account is not on this Louvre’s list. Ask its operator to add you.',
    failed: 'GitHub did not finish the sign-in. Try again.',
}

/** What the sign-in form needs to know beyond the session. */
export interface SignInProps {
    /** Why the last sign-in came back unfinished, as the server says it in ?sign_in=. */
    why?: string | undefined
    /** The page to come back to once signed in; the page the form is on unless given. */
    next?: string | undefined
}

/** The ways to sign in this deployment offers: GitHub, and by name where it allows that. */
export function SignIn({ why, next }: SignInProps) {
    const { data: session } = useQuery(sessionQuery)
    const { byName } = useSignIn()
    const navigate = useNavigate()
    const here = useLocation({ select: (location) => location.href })
    const [login, setLogin] = useState('')
    if (!session) {
        return null
    }
    const said = why ? WHY[why] : undefined
    const then = localPath(next ?? here)
    const github = then === '/' ? '/auth/github' : `/auth/github?${new URLSearchParams({ next: then }).toString()}`
    return (
        <div className="grid gap-6">
            {said ? (
                <p role="alert" className="font-ui text-sm text-accent">
                    {said}
                </p>
            ) : null}
            {session.sign_in.github ? (
                <a className="button" href={github}>
                    Sign in with GitHub
                </a>
            ) : null}
            {session.sign_in.dev ? (
                <form
                    className="grid gap-2"
                    onSubmit={(event) => {
                        event.preventDefault()
                        const name = login.trim().toLowerCase()
                        if (name) {
                            byName.mutate(name, { onSuccess: () => void navigate({ href: then }) })
                        }
                    }}
                >
                    <label className="label" htmlFor="sign-in-name">
                        Sign in by name (this deployment allows it)
                    </label>
                    <div className="flex gap-3">
                        <input
                            id="sign-in-name"
                            className="field min-w-0 flex-1"
                            value={login}
                            onChange={(event) => setLogin(event.target.value)}
                            placeholder="your-name"
                            autoComplete="username"
                            pattern="[a-zA-Z0-9][a-zA-Z0-9\-]*"
                            maxLength={39}
                        />
                        <button type="submit" className="button" disabled={byName.isPending}>
                            Sign in
                        </button>
                    </div>
                    {byName.error ? <p className="font-ui text-sm text-accent">{byName.error.message}</p> : null}
                </form>
            ) : null}
            {!session.sign_in.github && !session.sign_in.dev ? (
                <p className="text-muted">
                    No way to sign in is set up yet: the operator sets LOUVRE_GITHUB_CLIENT_ID and
                    LOUVRE_GITHUB_CLIENT_SECRET (docs/DEPLOY.md).
                </p>
            ) : null}
        </div>
    )
}

/** A link to the sign-in page that brings the person back to the page it is on once they are signed in. */
export function SignInLink({ className, children }: { className: string; children: ReactNode }) {
    const { pathname, href } = useLocation()
    const next = localPath(href)
    // On the sign-in page already, the page to come back to stays the one it was given.
    const search = pathname === '/sign-in' ? true : next === '/' ? {} : { next }
    return (
        <Link to="/sign-in" search={search} className={className}>
            {children}
        </Link>
    )
}
