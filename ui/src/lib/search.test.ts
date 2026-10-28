import { describe, expect, it } from 'vitest'

import { catalogueSearch, MAX_QUERY } from './search'

describe('catalogueSearch', () => {
    it('keeps an origin of strings', () => {
        expect(catalogueSearch({ origin: { 'canopy.ticket': 'PAY-142' } })).toEqual({
            origin: { 'canopy.ticket': 'PAY-142' },
        })
    })

    it('drops an origin that is not an object of strings, or has no pair', () => {
        for (const origin of ['PAY-142', ['PAY-142'], null, {}, { 'canopy.ticket': 142 }]) {
            expect(catalogueSearch({ origin })).toEqual({})
        }
        expect(catalogueSearch({})).toEqual({})
    })

    it('keeps words to search for, trimmed, beside an origin', () => {
        expect(catalogueSearch({ q: '  fraud check ', origin: { 'canopy.ticket': 'PAY-142' } })).toEqual({
            origin: { 'canopy.ticket': 'PAY-142' },
            q: 'fraud check',
        })
    })

    it('drops a search that is blank, not words, or too long', () => {
        for (const q of ['', '   ', 142, ['fraud'], 'x'.repeat(MAX_QUERY + 1)]) {
            expect(catalogueSearch({ q })).toEqual({})
        }
    })
})
