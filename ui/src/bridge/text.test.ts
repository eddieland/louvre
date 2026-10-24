import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { anchorOf, collapse, locate, quote, readText } from './text'

// The cases louvre.core.text answers too (tests/louvre/core/test_text.py reads the same file).

interface Case {
    name: string
    html: string[]
    text: string
    anchors: { exact: string; prefix?: string; suffix?: string; at: number | null }[]
}

const FIXTURES = resolve(import.meta.dirname, '../../../tests/fixtures/anchors.json')
const { cases } = JSON.parse(readFileSync(FIXTURES, 'utf8')) as { cases: Case[] }

function page(html: string): Document {
    return new DOMParser().parseFromString(html, 'text/html')
}

describe('readText', () => {
    it.each(cases.map((c) => [c.name, c] as const))('%s', (_name, found) => {
        const doc = page(found.html.join(''))
        const { text } = readText(doc.documentElement)

        expect(text).toBe(found.text)
        for (const anchor of found.anchors) {
            expect(locate(text, anchorOf(anchor.exact, anchor.prefix, anchor.suffix))).toBe(anchor.at)
        }
    })

    // Mapping between the text and the page's Ranges is held in Chromium by tests/louvre/web/test_flows.py:
    // happy-dom's Range moves its start when its end is set.

    it("skips Louvre's own elements", () => {
        const doc = page('<p>seen</p><div data-louvre>1</div>')
        expect(readText(doc.documentElement, (e) => e instanceof HTMLElement && 'louvre' in e.dataset).text).toBe(
            'seen',
        )
    })
})

describe('quote', () => {
    it('keeps up to 32 characters either side, collapsed', () => {
        const text = `${'a'.repeat(40)} passage ${'b'.repeat(40)}`
        const at = text.indexOf('passage')

        expect(quote(text, at, at + 7)).toEqual({ exact: 'passage', prefix: 'a'.repeat(31), suffix: 'b'.repeat(31) })
    })

    it('collapses like the server', () => {
        expect(collapse('  a \n\t b  ')).toBe('a b')
    })
})
