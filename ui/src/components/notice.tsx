import type { ReactNode } from 'react'

/** A page's whole message when it has nothing else to show: no database, nothing published, or no access. */
export function Notice({ title, children }: { title: string; children: ReactNode }) {
    return (
        <section className="catalogue">
            <h1 className="title">{title}</h1>
            <div className="mt-4 grid max-w-prose gap-3 text-muted">{children}</div>
        </section>
    )
}
