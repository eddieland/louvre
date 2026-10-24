import { describe, expect, it } from 'vitest'

import type { Decision } from '@/lib/api'
import { labelOf, passageId, rank, summary, waiting } from '@/lib/decisions'

function decision(changes: Partial<Decision> = {}): Decision {
    return {
        id: 'd_1',
        artifact_id: 'a_1',
        artifact_title: 'Checkout',
        question: 'Which fix ships first?',
        multiple: false,
        version: 1,
        options: [
            { id: 'o1', label: 'Batch', detail: '', anchor: null, count: 1 },
            { id: 'o2', label: 'Warm', detail: '', anchor: null, count: 0 },
        ],
        asked: [
            { login: 'ana', name: 'Ana Ruiz', answered: true },
            { login: 'raj', name: null, answered: false },
        ],
        author: { id: 'agent:sam:w', display_name: 'w', kind: 'agent', on_behalf_of: 'sam' },
        state: 'open',
        outcome: null,
        outcome_note: '',
        created_at: '2026-10-24T00:00:00.000Z',
        closed_at: null,
        answers: [
            {
                account_id: 'ana',
                name: 'Ana Ruiz',
                choices: ['o1'],
                note: '',
                answered_at: '2026-10-24T00:00:00.000Z',
            },
        ],
        mine: null,
        awaits_me: false,
        may_close: false,
        ...changes,
    }
}

describe('decisions', () => {
    it('says who it still waits on, by name or else by login', () => {
        expect(waiting(decision())).toBe('1 answer. Waiting on raj.')
        expect(waiting(decision({ state: 'closed' }))).toBe('1 answer.')
        const both = decision({ asked: [...decision().asked, { login: 'sam', name: 'Sam Okafor', answered: false }] })
        expect(waiting(both, 'Sam')).toBe('1 answer. Waiting on you, raj.')
    })

    it('sums up where it stands in a line', () => {
        expect(summary(decision())).toBe('2 options. 1 answer. Waiting on raj.')
        expect(summary(decision({ mine: { choices: ['o2'], note: '' } }))).toBe(
            'You chose Warm. 1 answer. Waiting on raj.',
        )
        expect(summary(decision({ state: 'closed' }))).toBe('1 answer')
    })

    it('names an option, or gives back an id it does not offer', () => {
        expect(labelOf(decision(), 'o2')).toBe('Warm')
        expect(labelOf(decision(), 'o9')).toBe('o9')
    })

    it('marks each option apart, and sorts what awaits the reader first', () => {
        const d = decision()
        const [first] = d.options
        expect(first && passageId(d, first)).toBe('option:d_1:o1')
        const order = [decision({ state: 'closed' }), decision(), decision({ awaits_me: true })].map((x) => rank(x))
        expect(order).toStrictEqual([2, 1, 0])
    })
})
