import { describe, expect, it } from 'vitest'

import type { Activity, Present } from './api'
import { doing, named, replyingIn } from './presence'

function present(name: string, activity: Activity, threadId: string | null = null): Present {
    return {
        author: { id: `agent:dev:sam:${name}`, display_name: name, kind: 'agent', on_behalf_of: 'dev:sam' },
        activity,
        note: '',
        thread_id: threadId,
        since: '2026-10-30T12:00:00Z',
        seen_at: '2026-10-30T12:00:00Z',
        expires_at: '2026-10-30T12:05:00Z',
    }
}

/** Thread t1 is the margin's second; it shows no other. */
function numberOf(id: string): number | null {
    return id === 't1' ? 2 : null
}

describe('presence', () => {
    it('says what each agent is doing', () => {
        expect(doing(present('worker', 'here'), numberOf)).toBe('is here')
        expect(doing(present('worker', 'reading'), numberOf)).toBe('is reading')
        expect(doing(present('worker', 'revising'), numberOf)).toBe('is revising this page')
    })

    it('names the thread an agent replies in by its number, when the margin shows it', () => {
        expect(doing(present('worker', 'replying', 't1'), numberOf)).toBe('is replying in thread 2')
        expect(doing(present('worker', 'replying', 't9'), numberOf)).toBe('is replying')
    })

    it('finds the agents replying in a thread', () => {
        const all = [present('a', 'replying', 't1'), present('b', 'replying', 't2'), present('c', 'reading')]
        expect(replyingIn(all, 't1')).toEqual(['a'])
        expect(replyingIn(all, 't3')).toEqual([])
    })

    it('names three agents at most, and counts the rest', () => {
        const all = ['a', 'b', 'c', 'd', 'e'].map((n) => present(n, 'here'))
        const { shown, more } = named(all)
        expect(shown.map((p) => p.author.display_name)).toEqual(['a', 'b', 'c'])
        expect(more).toBe(2)
        expect(named(all.slice(0, 2)).more).toBe(0)
    })
})
