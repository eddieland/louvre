import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

// Every color token that is text, read against what it sits on, in both themes, at WCAG AA for small text
// (ui/DESIGN.md, "Tokens"). The values are the hex ones tokens.css writes.

const AA = 4.5
const TEXT = ['ink', 'muted', 'accent']
const BASES = ['wall', 'paper']

const css = readFileSync(resolve(import.meta.dirname, 'tokens.css'), 'utf8')
const DARK = block(/^:root \{([^}]*)\}/mu)
const LIGHT = block(/^:root\[data-theme='light'\] \{([^}]*)\}/mu)
const SYSTEM_LIGHT = block(/^ {4}:root:not\(\[data-theme='dark'\]\) \{([^}]*)\}/mu)

describe('tokens', () => {
    it.each([
        ['dark', DARK],
        ['light', LIGHT],
    ])('every text token reads at AA on every base, %s', (_name, theme) => {
        for (const text of TEXT) {
            for (const base of BASES) {
                expect(contrast(hex(theme, text), hex(theme, base)), `${text} on ${base}`).toBeGreaterThanOrEqual(AA)
            }
        }
    })

    it('accent-ink reads on the accent in both themes', () => {
        for (const theme of [DARK, LIGHT]) {
            expect(contrast(hex(theme, 'accent-ink'), hex(theme, 'accent'))).toBeGreaterThanOrEqual(AA)
        }
    })

    it('the system light theme and the chosen one are the same values', () => {
        expect(SYSTEM_LIGHT).toStrictEqual(LIGHT)
    })

    it('both themes name the same tokens', () => {
        expect(Object.keys(LIGHT).toSorted()).toStrictEqual(Object.keys(DARK).toSorted())
    })
})

function block(pattern: RegExp): Record<string, string> {
    const match = pattern.exec(css)
    if (!match?.[1]) {
        throw new Error(`tokens.css has no block matching ${String(pattern)}`)
    }
    return Object.fromEntries(
        [...match[1].matchAll(/--([\w-]+):\s*([^;]+);/gu)].map(([, name = '', value = '']) => [name, value.trim()]),
    )
}

function hex(theme: Record<string, string>, name: string): [number, number, number] {
    const value = theme[name] ?? ''
    const match = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/u.exec(value)
    if (!match) {
        throw new Error(`--${name} is not a six-digit hex color: ${value}`)
    }
    return [match[1], match[2], match[3]].map((part) => Number.parseInt(part ?? '0', 16)) as [number, number, number]
}

function luminance([r, g, b]: [number, number, number]): number {
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

function channel(value: number): number {
    const s = value / 255
    return s <= 0.039_28 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}

function contrast(a: [number, number, number], b: [number, number, number]): number {
    const [hi, lo] = [luminance(a), luminance(b)].toSorted((x, y) => y - x)
    return ((hi ?? 0) + 0.05) / ((lo ?? 0) + 0.05)
}
