import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'

import { Header } from '@/components/header'
import { Notice } from '@/components/notice'
import { SignIn } from '@/components/sign-in'
import { Footer, Words } from '@/components/site'
import { request, sessionQuery, tokensQuery } from '@/lib/api'
import type { Token } from '@/lib/api'
import { ago } from '@/lib/format'
import { usePageTitle } from '@/lib/title'

/** The scopes a token may have, and what each lets its agent do. */
const SCOPES = [
    { scope: 'read', says: 'read artifacts and threads' },
    { scope: 'publish', says: 'publish artifacts and versions' },
    { scope: 'comment', says: 'comment, reply, and resolve' },
] as const

/** A person's tokens for their agents: mint one, see each, revoke one (REQUIREMENTS L4). */
export const Route = createFileRoute('/tokens')({
    component: Tokens,
})

function Tokens() {
    const session = useQuery(sessionQuery)
    const account = session.data?.account ?? null
    const tokens = useQuery({ ...tokensQuery, enabled: account !== null })
    usePageTitle('Tokens')
    if (session.isPending) {
        return <Header />
    }
    if (!account) {
        return (
            <>
                <Header />
                <main>
                    <Notice title="Sign in to mint tokens">
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
            <main className="catalogue">
                <h1 className="title">Tokens</h1>
                <p className="mt-3 max-w-prose text-muted">
                    A token lets one agent reach Louvre&rsquo;s MCP server for you, in one namespace, with the scopes
                    you give it. Its comments show as the agent&rsquo;s, for you.
                </p>
                <Words
                    paragraphs={session.data?.site.tokens ?? []}
                    className="mt-3 grid max-w-prose gap-3 text-muted"
                />
                <Mint login={account.login} />
                <h2 className="mt-12 heading">Yours</h2>
                {tokens.data?.tokens.length === 0 ? <p className="mt-3 text-muted">None yet.</p> : null}
                <ul className="mt-3 border-t border-rule">
                    {tokens.data?.tokens.map((token) => (
                        <Row key={token.id} token={token} />
                    ))}
                </ul>
            </main>
            <Footer />
        </>
    )
}

function Mint({ login }: { login: string }) {
    const client = useQueryClient()
    const [name, setName] = useState('canopy worker')
    const [namespace, setNamespace] = useState(`canopy/${login.toLowerCase()}`)
    const [scopes, setScopes] = useState<Set<string>>(() => new Set(['read', 'publish', 'comment']))
    const mint = useMutation({
        mutationFn: () =>
            request<{ token: Token; secret: string }>('POST', '/api/tokens', { name, namespace, scopes: [...scopes] }),
        onSuccess: () => client.invalidateQueries({ queryKey: tokensQuery.queryKey }),
    })
    const minted = mint.data
    return (
        <section className="mt-8 grid gap-4" aria-labelledby="mint-title">
            <h2 id="mint-title" className="heading">
                Mint a token
            </h2>
            <form
                className="grid gap-4"
                onSubmit={(event) => {
                    event.preventDefault()
                    mint.mutate()
                }}
            >
                <div className="grid gap-4 sm:grid-cols-2">
                    <label className="grid gap-1">
                        <span className="label">Agent&rsquo;s name</span>
                        <input className="field" value={name} onChange={(e) => setName(e.target.value)} required />
                    </label>
                    <label className="grid gap-1">
                        <span className="label">Namespace</span>
                        <input
                            className="field"
                            value={namespace}
                            onChange={(e) => setNamespace(e.target.value)}
                            required
                        />
                    </label>
                </div>
                <fieldset className="grid gap-2">
                    <legend className="label mb-1">Scopes</legend>
                    {SCOPES.map(({ scope, says }) => (
                        <label key={scope} className="flex items-baseline gap-2 font-ui text-sm">
                            <input
                                type="checkbox"
                                className="accent-accent"
                                checked={scopes.has(scope)}
                                onChange={(e) => {
                                    const next = new Set(scopes)
                                    if (e.target.checked) {
                                        next.add(scope)
                                    } else {
                                        next.delete(scope)
                                    }
                                    setScopes(next)
                                }}
                            />
                            <span className="text-ink">{scope}</span>
                            <span className="text-muted">{says}</span>
                        </label>
                    ))}
                </fieldset>
                <div>
                    <button type="submit" className="button" disabled={mint.isPending || scopes.size === 0}>
                        Mint
                    </button>
                </div>
                {mint.error ? (
                    <p role="alert" className="font-ui text-sm text-accent">
                        {mint.error.message}
                    </p>
                ) : null}
            </form>
            {minted ? <Minted secret={minted.secret} /> : null}
        </section>
    )
}

function Minted({ secret }: { secret: string }) {
    const url = `${globalThis.location.origin}/mcp`
    const config = JSON.stringify(
        { mcpServers: { louvre: { type: 'http', url, headers: { Authorization: `Bearer ${secret}` } } } },
        null,
        2,
    )
    const command = `claude mcp add --transport http louvre ${url} --header "Authorization: Bearer ${secret}"`
    return (
        <output className="minted">
            <p className="font-ui text-sm">
                <span className="text-accent">Copy it now:</span> this is the only time Louvre shows this token.
            </p>
            <Copyable label="Token" text={secret} />
            <Copyable label="Claude Code" text={command} />
            <Copyable label="An MCP client's config" text={config} />
        </output>
    )
}

function Copyable({ label, text }: { label: string; text: string }) {
    const [copied, setCopied] = useState(false)
    return (
        <div className="grid gap-1">
            <div className="flex items-baseline justify-between gap-3">
                <span className="label">{label}</span>
                <button
                    type="button"
                    className="action"
                    onClick={() => {
                        void navigator.clipboard.writeText(text).then(() => setCopied(true))
                    }}
                >
                    {copied ? 'Copied' : 'Copy'}
                </button>
            </div>
            <pre className="code">{text}</pre>
        </div>
    )
}

function Row({ token }: { token: Token }) {
    const client = useQueryClient()
    const revoke = useMutation({
        mutationFn: () => request('DELETE', `/api/tokens/${encodeURIComponent(token.id)}`),
        onSettled: () => client.invalidateQueries({ queryKey: tokensQuery.queryKey }),
    })
    const revoked = token.revoked_at !== null
    return (
        <li className="entry-row">
            <div className="min-w-0">
                <p className={revoked ? 'text-muted line-through' : ''}>
                    {token.name} <span className="font-ui text-sm text-muted">in {token.namespace}</span>
                </p>
                <p className="font-ui text-xs text-muted">
                    {token.scopes.join(', ')} &middot; made {ago(token.created_at)} &middot;{' '}
                    {token.last_used_at ? `used ${ago(token.last_used_at)}` : 'never used'}
                    {token.revoked_at ? ` · revoked ${ago(token.revoked_at)}` : ''}
                </p>
            </div>
            {revoked ? null : (
                <button type="button" className="action" onClick={() => revoke.mutate()} disabled={revoke.isPending}>
                    Revoke
                </button>
            )}
        </li>
    )
}
