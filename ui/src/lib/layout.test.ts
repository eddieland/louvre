import { describe, expect, it } from 'vitest'

import { place } from './layout'

describe('place', () => {
    it('sets each thread level with its passage when nothing overlaps', () => {
        expect(
            place(
                [
                    { id: 'a', want: 10, height: 40 },
                    { id: 'b', want: 200, height: 40 },
                ],
                null,
            ),
        ).toEqual([10, 200])
    })

    it('moves a thread below the one before it when they would overlap', () => {
        const items = [
            { id: 'a', want: 10, height: 100 },
            { id: 'b', want: 50, height: 40 },
        ]
        expect(place(items, null, 12)).toEqual([10, 122])
    })

    it('keeps the active thread at its passage, and moves the one before it up', () => {
        const items = [
            { id: 'a', want: 100, height: 100 },
            { id: 'b', want: 150, height: 40 },
        ]
        expect(place(items, 'b', 12)).toEqual([38, 150])
    })

    it('never sets a thread above the margin', () => {
        const items = [
            { id: 'a', want: 0, height: 100 },
            { id: 'b', want: 20, height: 40 },
        ]
        expect(place(items, 'b', 12)).toEqual([0, 112])
    })
})
