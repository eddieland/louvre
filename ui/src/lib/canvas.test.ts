import { describe, expect, it } from 'vitest'

import { bounds, fit, live, MAX_SCALE, MIN_SCALE, panBy, wheelFactor, zoomAt } from './canvas'

describe('bounds', () => {
    it('holds every box, with room above for their labels', () => {
        expect(
            bounds(
                [
                    { x: 0, y: 0, width: 1440, height: 900 },
                    { x: 1600, y: 1060, width: 390, height: 844 },
                ],
                40,
            ),
        ).toEqual({ x: 0, y: -40, width: 1990, height: 1944 })
    })

    it('is empty for no boxes', () => {
        expect(bounds([])).toEqual({ x: 0, y: 0, width: 0, height: 0 })
    })
})

describe('fit', () => {
    it('scales the canvas to the narrower room, and centers it', () => {
        const view = fit({ x: 0, y: 0, width: 2000, height: 1000 }, 1000, 1000, 0)

        expect(view.scale).toBe(0.5)
        expect(view.x).toBe(0)
        expect(view.y).toBe(250)
    })

    it('leaves the padding around the canvas', () => {
        const view = fit({ x: 100, y: 100, width: 800, height: 800 }, 1000, 1000, 100)

        expect(view).toEqual({ x: 0, y: 0, scale: 1 })
    })

    it('never zooms in past the pages at their own size', () => {
        expect(fit({ x: 0, y: 0, width: 10, height: 10 }, 1000, 1000, 0).scale).toBe(1)
    })
})

describe('zoomAt', () => {
    it('keeps the point it zooms about where it is on the screen', () => {
        const view = { x: 10, y: 20, scale: 0.5 }
        const at = { x: 300, y: 200 }
        const zoomed = zoomAt(view, 2, at)
        const canvasPoint = { x: (at.x - view.x) / view.scale, y: (at.y - view.y) / view.scale }

        expect(zoomed.scale).toBe(1)
        expect(zoomed.x + canvasPoint.x * zoomed.scale).toBeCloseTo(at.x)
        expect(zoomed.y + canvasPoint.y * zoomed.scale).toBeCloseTo(at.y)
    })

    it('stops at the least and the most scale', () => {
        expect(zoomAt({ x: 0, y: 0, scale: 0.1 }, 0.01, { x: 0, y: 0 }).scale).toBe(MIN_SCALE)
        expect(zoomAt({ x: 0, y: 0, scale: 1 }, 100, { x: 0, y: 0 }).scale).toBe(MAX_SCALE)
    })
})

describe('panBy', () => {
    it('moves the canvas by screen pixels, at any scale', () => {
        expect(panBy({ x: 5, y: 5, scale: 0.25 }, 10, -20)).toEqual({ x: 15, y: -15, scale: 0.25 })
    })
})

describe('wheelFactor', () => {
    it('zooms in for a turn up, and out for one down', () => {
        expect(wheelFactor(-100, 0, false)).toBeGreaterThan(1)
        expect(wheelFactor(100, 0, false)).toBeLessThan(1)
    })

    it('counts a line as pixels, so a mouse and a trackpad zoom alike', () => {
        expect(wheelFactor(3, 1, false)).toBeCloseTo(wheelFactor(48, 0, false))
    })
})

describe('live', () => {
    // The design study's board: a row a direction, its laptop beside its phone.
    const frames = [0, 1, 2].flatMap((row) => [
        { id: `laptop-${String(row)}`, x: 0, y: row * 1060, width: 1440, height: 900 },
        { id: `phone-${String(row)}`, x: 1600, y: row * 1060, width: 390, height: 844 },
    ])

    it('draws every page on a screen wider than a phone', () => {
        expect(ids(live(frames, { x: 0, y: 0, scale: 0.2 }, 1440, 780))).toEqual(ids(frames))
    })

    it('draws two pages on a phone with the board fitted to it: of the laptops it shows whole, the first two', () => {
        expect(ids(live(frames, fit(bounds(frames, 80), 390, 700, 24), 390, 700))).toEqual(['laptop-0', 'laptop-1'])
    })

    it('draws two pages at most on a phone, those it shows the most of first', () => {
        // All six show in part; the second row's phone the most, then the first row's.
        const shown = live(frames, { x: -440, y: -150, scale: 0.34 }, 390, 700)

        expect(ids(shown)).toEqual(['phone-1', 'phone-0'])
    })

    it('counts a phone on its side as a phone', () => {
        expect(live(frames, { x: 0, y: 0, scale: 0.1 }, 932, 330)).toHaveLength(2)
    })

    it('draws no page that is off the screen', () => {
        expect(live(frames, { x: -5000, y: 0, scale: 1 }, 390, 700)).toEqual([])
    })
})

function ids(boxes: readonly { id: string }[]): string[] {
    return boxes.map((box) => box.id)
}
