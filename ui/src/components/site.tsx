import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import type { Run } from '@/lib/api'
import { sessionQuery } from '@/lib/api'

/**
 * The owner's words, as paragraphs (louvre.web.site): text, links, and marks, drawn as elements, never as HTML, so
 * nothing the owner wrote runs as markup on Louvre's page. Nothing when there are none.
 */
export function Words({ paragraphs, className }: { paragraphs: Run[][]; className?: string }) {
    if (paragraphs.length === 0) {
        return null
    }
    return (
        <div className={className}>
            {paragraphs.map((runs, p) => (
                // oxlint-disable-next-line react/no-array-index-key -- the owner's paragraphs never move.
                <p key={p} className="whitespace-pre-line">
                    {runs.map((run, r) => (
                        // oxlint-disable-next-line react/no-array-index-key -- a paragraph's runs never move.
                        <Said key={r} run={run} />
                    ))}
                </p>
            ))}
        </div>
    )
}

function Said({ run }: { run: Run }) {
    let said: ReactNode = run.code ? <code>{run.text}</code> : run.text
    if (run.em) {
        said = <em>{said}</em>
    }
    if (run.strong) {
        said = <strong>{said}</strong>
    }
    if (run.href === undefined) {
        return said
    }
    // A page of Louvre's opens in place; another site's leaves Louvre's tab alone.
    const away = !run.href.startsWith('/')
    return (
        <a className="link" href={run.href} {...(away ? { target: '_blank', rel: 'noopener noreferrer' } : {})}>
            {said}
        </a>
    )
}

/** The owner's banner, above the header of every page (ui/DESIGN.md, "The owner's words"). */
export function Banner() {
    const { data: session } = useQuery(sessionQuery)
    const banner = session?.site.banner ?? []
    if (banner.length === 0) {
        return null
    }
    return (
        <aside className="banner" aria-label="From this deployment">
            <Words paragraphs={banner} />
        </aside>
    )
}

/** The owner's footer, at the foot of the pages that list things, and of signing in. */
export function Footer() {
    const { data: session } = useQuery(sessionQuery)
    const footer = session?.site.footer ?? []
    if (footer.length === 0) {
        return null
    }
    return (
        <footer className="colophon">
            <Words paragraphs={footer} className="grid gap-2" />
        </footer>
    )
}
