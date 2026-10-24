import { describe, expect, it } from 'vitest'

import type { Comment, Comparison, Thread } from './api'
import { changeMarks, fateOf, kindOf, notesOf, tally } from './changes'

const COMPARISON: Comparison = {
    base: 1,
    head: 2,
    changes: [
        {
            kind: 'changed',
            anchor: { exact: 'five minutes', prefix: 'for', suffix: '' },
            added: 'five minutes',
            removed: '60 s',
        },
        { kind: 'removed', anchor: { exact: 'Move', prefix: 'time.', suffix: 'the' }, added: '', removed: 'A day.' },
        { kind: 'added', anchor: null, added: 'All new.', removed: '' },
    ],
    words_added: 4,
    words_removed: 4,
    threads: [],
}

function comment(created_at: string, deleted = false): Comment {
    return {
        id: created_at,
        thread_id: 't1',
        author: { id: 'dev:ana', display_name: 'Ana', kind: 'person', on_behalf_of: null },
        body: deleted ? '' : 'Said.',
        created_at,
        edited_at: null,
        deleted_at: deleted ? created_at : null,
        via: 'web',
    }
}

function thread(state: Thread['state'], comments: Comment[]): Thread {
    return { id: 't1', anchor: null, anchored_version: 1, state, anchor_status: null, comments }
}

describe('changes', () => {
    it('gives each change an id, and marks only what the later version shows', () => {
        const notes = notesOf(COMPARISON)

        expect(notes.map((n) => n.id)).toEqual(['change-1', 'change-2', 'change-3'])
        expect(changeMarks(notes)).toEqual([
            { id: 'change-1', anchor: COMPARISON.changes[0]?.anchor, state: 'change', n: null },
            { id: 'change-2', anchor: COMPARISON.changes[1]?.anchor, state: 'removed', n: null },
        ])
        expect(notes.map((n) => kindOf(n))).toEqual(['Rewritten', 'Removed', 'Added'])
    })

    it('tallies changes and words, the unit once', () => {
        expect(tally(COMPARISON)).toBe('3 changes: 4 words added, 4 removed')
        expect(
            tally({ ...COMPARISON, changes: COMPARISON.changes.slice(0, 1), words_added: 0, words_removed: 1 }),
        ).toBe('1 change: 1 word removed')
        expect(tally({ ...COMPARISON, changes: [], words_added: 0, words_removed: 0 })).toBe('The text did not change.')
    })

    it("says what became of a thread's passage, whether it is resolved, and its replies since", () => {
        const since = '2026-10-23T12:00:00.000Z'
        const replied = thread('resolved', [
            comment('2026-10-23T11:00:00.000Z'),
            comment('2026-10-23T11:30:00.000Z'),
            comment('2026-10-23T13:00:00.000Z'),
            comment('2026-10-23T14:00:00.000Z', true),
        ])
        const gone = { thread_id: 't1', state: 'open', outcome: 'passage_gone' } as const

        expect(fateOf(gone, replied, since)).toBe('Passage reworded or removed · resolved · 1 reply since')
        // The first comment opened the thread, after the earlier version or not: it is no reply.
        expect(fateOf({ ...gone, outcome: null }, thread('open', [comment('2026-10-23T13:00:00.000Z')]), since)).toBe(
            'On the whole page',
        )
        expect(fateOf({ ...gone, outcome: 'near_change' }, undefined, since)).toBe('Changed beside its passage')
        expect(fateOf({ ...gone, outcome: 'unchanged', state: 'resolved' }, undefined, since)).toBe(
            'Passage unchanged · resolved',
        )
    })
})
