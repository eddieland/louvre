// What changed from one version to a later one, as the artifact page shows it (ui/DESIGN.md, "Changes"): each change
// marked in the frame and noted in the margin level with it, and above them what became of the earlier threads.

import type { Mark } from '@/bridge/protocol'
import type { Change, Comparison, Thread, ThreadFate } from '@/lib/api'
import { count } from '@/lib/format'

/** A change as the margin notes it: the server's, with an id of its own for its mark and its note. */
export interface MarkedChange extends Change {
    /** Unique on the page, never a thread's: `change-` and its place in the later version's order. */
    id: string
}

/** The margin's summary of a comparison, which sits above its changes. */
export const SUMMARY = 'summary'

/** What became of a thread's passage, as the summary says it; `page` for a thread on the whole page. */
const PASSAGES: Record<NonNullable<ThreadFate['outcome']> | 'page', string> = {
    unchanged: 'Passage unchanged',
    near_change: 'Changed beside its passage',
    passage_gone: 'Passage reworded or removed',
    page: 'On the whole page',
}
/** What the margin calls each kind of change. */
const KINDS: Record<Change['kind'], string> = { added: 'Added', removed: 'Removed', changed: 'Rewritten' }

/** Give each change an id for its mark and its note. */
export function notesOf(comparison: Comparison): MarkedChange[] {
    return comparison.changes.map((change, i) => ({ ...change, id: `change-${String(i + 1)}` }))
}

/** The marks the bridge is asked for: words added or rewritten are painted; a removal is only found, to place it. */
export function changeMarks(notes: readonly MarkedChange[]): Mark[] {
    const marks: Mark[] = []
    for (const note of notes) {
        if (note.anchor) {
            // A change is in a version's words, never at a place on a map.
            const state = note.kind === 'removed' ? 'removed' : 'change'
            marks.push({ id: note.id, anchor: note.anchor, place: null, state, n: null })
        }
    }
    return marks
}

/** What the margin calls a change, such as "Rewritten". */
export function kindOf(change: Change): string {
    return KINDS[change.kind]
}

/** Say how much changed, such as "3 changes: 9 words added, 7 removed", or that the text did not change. */
export function tally(comparison: Comparison): string {
    const { changes, words_added: added, words_removed: removed } = comparison
    if (changes.length === 0) {
        return 'The text did not change.'
    }
    // "9 words added, 7 removed": the unit once, on the first count.
    const words = [
        added > 0 ? `${count(added, 'word')} added` : '',
        removed > 0 ? `${added > 0 ? String(removed) : count(removed, 'word')} removed` : '',
    ]
    return `${count(changes.length, 'change')}: ${words.filter(Boolean).join(', ')}`
}

/**
 * Say what became of a thread since the earlier version, such as "Passage reworded or removed · resolved · 1 reply
 * since": its passage, then whether it is resolved, then how many replies came after the earlier version did.
 */
export function fateOf(fate: ThreadFate, thread: Thread | undefined, since: string): string {
    const passage = PASSAGES[fate.outcome ?? 'page']
    const after = Date.parse(since)
    // Its first comment opened it, on the earlier version or one before: what came after it are its replies.
    const replies = (thread?.comments ?? [])
        .slice(1)
        .filter((c) => c.deleted_at === null && Date.parse(c.created_at) > after)
    return [
        passage,
        // The threads are read again while the page is open; the comparison is not.
        (thread?.state ?? fate.state) === 'resolved' ? 'resolved' : '',
        replies.length > 0 ? `${count(replies.length, 'reply', 'replies')} since` : '',
    ]
        .filter(Boolean)
        .join(' · ')
}
