import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useState } from 'react'

import { sessionQuery, useSignIn } from '@/lib/api'

/** Why a sign-in came back unfinished, as the server says it in ?sign_in=. */
const WHY: Record<string, string> = {
    denied: 'That GitHub account is not on this Louvre’s list. Ask its operator to add you.',
    failed: 'GitHub did not finish the sign-in. Try again.',
}

/** The ways to sign in this deployment offers: GitHub, and by name where it allows that. */
export function SignIn({ why }: { why?: string | undefined }) {
    const { data: session } = useQuery(sessionQuery)
    const { byName } = useSignIn()
    const navigate = useNavigate()
    const [login, setLogin] = useState('')
    if (!session) {
        return null
    }
    const said = why ? WHY[why] : undefined
    return (
        <div className="grid gap-6">
            {said ? (
                <p role="alert" className="font-ui text-sm text-accent">
                    {said}
                </p>
            ) : null}
            {session.sign_in.github ? (
                <a className="button" href="/auth/github">
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
                            byName.mutate(name, { onSuccess: () => void navigate({ to: '/' }) })
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
            {session.configured ? (
                session.sign_in.github || session.sign_in.dev ? null : (
                    <p className="text-muted">
                        No way to sign in is set up yet: the operator sets LOUVRE_GITHUB_CLIENT_ID and
                        LOUVRE_GITHUB_CLIENT_SECRET (docs/DEPLOY.md).
                    </p>
                )
            ) : (
                <p className="text-muted">
                    Signing in needs the database, and this deployment has none yet: it serves the demo from memory. The
                    operator sets DATABASE_URL, or connects a Postgres store in Vercel (docs/DEPLOY.md).
                </p>
            )}
        </div>
    )
}
