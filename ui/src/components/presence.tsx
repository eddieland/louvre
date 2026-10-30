import type { Present } from '@/lib/api'
import { count } from '@/lib/format'
import { doing, named } from '@/lib/presence'

/** What the presence line shows. */
export interface PresenceLineProps {
    /** The agents at work on the artifact now, the longest at it first. */
    present: readonly Present[]
    /** A thread's number in the margin, or null for one it does not show. */
    numberOf: (threadId: string) => number | null
}

/**
 * The agents at work on an artifact now, under the toolbar (ui/DESIGN.md, "Presence"): a line each, a disc in
 * `accent`, as what is live is, then the agent marked as an agent, what it is doing, and what it said of it. A polite
 * live region, so a screen reader hears an agent arrive or change what it does; empty, it takes no room.
 */
export function PresenceLine({ present, numberOf }: PresenceLineProps) {
    const { shown, more } = named(present)
    return (
        <output className="presence">
            {shown.map((p) => (
                <span key={p.author.id} className="presence-agent">
                    <span className="presence-dot" aria-hidden="true" />
                    <span className="who">{p.author.display_name}</span>{' '}
                    <em className="agent-badge">
                        (Agent
                        <span className="long">
                            {p.author.on_behalf_of_name ? `, for ${p.author.on_behalf_of_name}` : ''}
                        </span>
                        )
                    </em>{' '}
                    {doing(p, numberOf)}
                    {p.note ? <span className="presence-note">: {p.note}</span> : null}
                </span>
            ))}
            {more > 0 ? <span className="presence-agent">And {count(more, 'more agent')} at work</span> : null}
        </output>
    )
}
