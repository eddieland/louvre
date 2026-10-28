import { describe, expect, it } from 'vitest'

import { ago, count, provenance, roman, whereSaid } from './format'

describe('format', () => {
    const now = Date.parse('2026-10-23T12:00:00Z')

    it('says how long ago a time was', () => {
        expect(ago('2026-10-23T11:59:30Z', now)).toBe('just now')
        expect(ago('2026-10-23T09:00:00Z', now)).toBe('3 hours ago')
        expect(ago('2026-10-22T12:00:00Z', now)).toBe('yesterday')
    })

    it('writes versions in roman numerals', () => {
        expect([1, 2, 3, 4, 9, 14, 40].map((n) => roman(n))).toEqual(['I', 'II', 'III', 'IV', 'IX', 'XIV', 'XL'])
    })

    it('names an origin by its ticket first', () => {
        expect(provenance({ 'canopy.repo': 'payments', 'canopy.ticket': 'PAY-142' })).toBe('PAY-142')
        expect(provenance({ zeta: 'z', alpha: 'a' })).toBe('a')
        expect(provenance({})).toBeNull()
    })

    it('counts', () => {
        expect(count(1, 'thread')).toBe('1 thread')
        expect(count(2, 'reply', 'replies')).toBe('2 replies')
    })

    it('says a point as the server quotes one, with how sure a reading of it is', () => {
        expect(whereSaid([-9.13987, 38.71238], null)).toBe('38.71238° N, 9.13987° W')
        expect(whereSaid([151.2093, -33.8688], 1200.2)).toBe('33.86880° S, 151.20930° E, within 1,201 m')
    })
})
