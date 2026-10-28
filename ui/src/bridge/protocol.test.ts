import { describe, expect, it } from 'vitest'

import { mapPlaceOf } from './protocol'

describe('mapPlaceOf', () => {
    it('reads a feature, a point, and a box, as the map kit reports them', () => {
        expect(mapPlaceOf({ kind: 'feature', id: 'pole-102' })).toEqual({
            kind: 'feature',
            id: 'pole-102',
            coordinates: null,
        })
        expect(mapPlaceOf({ kind: 'point', coordinates: [-9.14, 38.71] })).toEqual({
            kind: 'point',
            id: '',
            coordinates: [-9.14, 38.71],
            accuracy: null,
        })
        expect(mapPlaceOf({ kind: 'box', coordinates: [-9.15, 38.7, -9.13, 38.72] })).toEqual({
            kind: 'box',
            id: '',
            coordinates: [-9.15, 38.7, -9.13, 38.72],
        })
    })

    it('reads a point with how sure a reading of it is, and none that is no number of metres', () => {
        const here = { kind: 'point', coordinates: [-9.14, 38.71] }
        expect(mapPlaceOf({ ...here, accuracy: 12 })).toMatchObject({ accuracy: 12 })
        expect(mapPlaceOf({ ...here, accuracy: -3 })).toMatchObject({ accuracy: null })
        expect(mapPlaceOf({ ...here, accuracy: '12' })).toMatchObject({ accuracy: null })
    })

    it('reads no box with no area, off the earth, or with too few sides', () => {
        expect(mapPlaceOf({ kind: 'box', coordinates: [-9.13, 38.7, -9.15, 38.72] })).toBeNull()
        expect(mapPlaceOf({ kind: 'box', coordinates: [-9.15, 38.7, -9.13, 38.7] })).toBeNull()
        expect(mapPlaceOf({ kind: 'box', coordinates: [-9.15, 38.7, -9.13, 91] })).toBeNull()
        expect(mapPlaceOf({ kind: 'box', coordinates: [-9.15, 38.7] })).toBeNull()
        expect(mapPlaceOf({ kind: 'point', coordinates: [-9.15, 38.7, -9.13, 38.72] })).toBeNull()
    })
})
