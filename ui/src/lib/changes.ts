// What changed from one version to a later one, as the artifact page shows it (ui/DESIGN.md, "Changes"): each change
// marked in the frame and noted in the margin level with it, and above them what became of the earlier threads. On a
// map, each feature the later version added, removed, or moved is lit on the map and noted too.

import type { Mark } from '@/bridge/protocol'
import type { Anchor } from '@/bridge/text'
import type { Change, Comparison, FeatureChange, Thread, ThreadFate } from '@/lib/api'
import { count } from '@/lib/format'

/** A change as the margin notes it: the server's, with an id of its own for its mark and its note. */
export interface MarkedChange extends Change {
    /** Unique on the page, never a thread's: `change-` and its place in the later version's order. */
    id: string
}

/** A feature a later version of a map changed, as the margin notes it, level with where the map lights it. */
export interface MarkedFeature {
    /** Unique on the page, never a thread's or a change of words': `feature-` and its place in the comparison. */
    id: string
    /** Its label as words, as a thread on it quotes them; the map kit places it, so it is never looked for. */
    anchor: Anchor
    /** The change, as the server said it. */
    feature: FeatureChange
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
/** What the margin calls each kind of change to a feature on a map. */
const FEATURE_KINDS: Record<FeatureChange['kind'], string> = { added: 'Added', removed: 'Removed', moved: 'Moved' }
/** The order a tally counts changes to features in: what moved first, as what a reader most likely looks for. */
const TALLIED: FeatureChange['kind'][] = ['moved', 'added', 'removed']
/** A metre, a kilometre, and the space that keeps a number on its unit's line (ui/DESIGN.md, "Type"). */
const KILOMETRE = 1000
const NBSP = '\u00A0'

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

/** Give each feature a later version of a map changed an id for its mark and its note. */
export function featureNotes(comparison: Comparison): MarkedFeature[] {
    return comparison.features.map((feature, i) => ({
        id: `feature-${String(i + 1)}`,
        anchor: { exact: feature.label, prefix: '', suffix: '' },
        feature,
    }))
}

/** The marks the bridge is asked for, for features changed: the map kit lights each where it was and where it is. */
export function featureMarks(notes: readonly MarkedFeature[]): Mark[] {
    return notes.map(({ id, anchor, feature }) => ({
        id,
        anchor,
        place: null,
        change: { kind: feature.kind, id: feature.id, geometry: feature.geometry, was: feature.was },
        state: 'change',
        n: null,
    }))
}

/** What the margin calls a change, such as "Rewritten", or a feature's, such as "Moved". */
export function kindOf(change: Change | FeatureChange): string {
    return 'label' in change ? FEATURE_KINDS[change.kind] : KINDS[change.kind]
}

/**
 * Say how far and which way a feature moved, such as "40 m north-east" or "1.2 km west", or that it was reshaped where
 * it was; empty for one added or removed.
 */
export function movedBy(feature: FeatureChange): string {
    if (feature.kind !== 'moved') {
        return ''
    }
    if (feature.metres === 0) {
        return 'Reshaped where it was'
    }
    const far =
        feature.metres < KILOMETRE
            ? `${String(feature.metres)}${NBSP}m`
            : `${(feature.metres / KILOMETRE).toFixed(1)}${NBSP}km`
    return `${far} ${feature.toward}`.trim()
}

/** Say how much changed, such as "3 changes: 9 words added, 7 removed", or that the text did not change. */
export function tally(comparison: Comparison): string {
    const { changes, features, words_added: added, words_removed: removed } = comparison
    if (changes.length === 0 && features.length === 0) {
        return 'The text did not change.'
    }
    // "9 words added, 7 removed": the unit once, on the first count.
    const words = [
        added > 0 ? `${count(added, 'word')} added` : '',
        removed > 0 ? `${added > 0 ? String(removed) : count(removed, 'word')} removed` : '',
    ]
    const text = changes.length > 0 ? `${count(changes.length, 'change')}: ${words.filter(Boolean).join(', ')}` : ''
    // "2 features moved, 1 added": the unit once too.
    const counted = TALLIED.map((kind) => [kind, features.filter((f) => f.kind === kind).length] as const)
    const onMap = counted
        .filter(([, n]) => n > 0)
        .map(([kind, n], i) => `${i === 0 ? count(n, 'feature') : String(n)} ${kind}`)
        .join(', ')
    return [text, onMap].filter(Boolean).join('; ')
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
