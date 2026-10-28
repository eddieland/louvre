import { describe, expect, it } from 'vitest'

import { catalogueSearch } from './search'

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
})
