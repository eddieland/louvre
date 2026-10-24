import type { Comparison, Thread } from '@/lib/api'
import { fateOf, SUMMARY, tally } from '@/lib/changes'
import { roman } from '@/lib/format'

/** What changed, in sum, and what became of each earlier thread. */
export interface ChangesSummaryProps {
    /** The comparison. */
    comparison: Comparison
    /** The artifact's threads, read in the later version, for each earlier thread's comments. */
    threads: Thread[]
    /** When the earlier version was published, as ISO 8601: replies after it are news. */
    since: string
    /** Whether it is the active note: on a narrow screen, the one the sheet shows. */
    active: boolean
    /** Leave the comparison for a thread, open on the page. */
    onOpenThread: (id: string) => void
}

/**
 * The margin's first note while comparing: how much changed, then each thread on the earlier version, by who started
 * it and what they said, with what became of its passage, whether it is resolved, and its replies since.
 */
export function ChangesSummary({ comparison, threads, since, active, onOpenThread }: ChangesSummaryProps) {
    const fates = comparison.threads.flatMap((fate) => {
        const thread = threads.find((t) => t.id === fate.thread_id)
        const first = thread?.comments[0]
        return thread && first ? [{ fate, thread, first }] : []
    })
    return (
        <section
            className={active ? 'thread changes-summary is-active' : 'thread changes-summary'}
            data-id={SUMMARY}
            aria-label="What changed"
        >
            <span className="change-kind">Since version {roman(comparison.base)}</span>
            <span className="changes-tally">{tally(comparison)}</span>
            {fates.length > 0 ? (
                <>
                    <span className="change-kind">Its threads</span>
                    <ul className="fates">
                        {fates.map(({ fate, thread, first }) => (
                            <li key={fate.thread_id}>
                                <button type="button" className="fate" onClick={() => onOpenThread(fate.thread_id)}>
                                    <span className="who">{first.author.display_name}</span>{' '}
                                    <span className="fate-body">{first.deleted_at ? 'Deleted.' : first.body}</span>
                                    <span className="fate-outcome" data-outcome={fate.outcome ?? 'page'}>
                                        {fateOf(fate, thread, since)}
                                    </span>
                                </button>
                            </li>
                        ))}
                    </ul>
                </>
            ) : null}
        </section>
    )
}
