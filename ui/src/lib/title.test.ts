import { describe, expect, it } from 'vitest'

import { titleOf } from './title'

describe('a tab’s title', () => {
    it('names the page, then the deployment, Louvre when its owner names it nothing', () => {
        expect(titleOf('Inbox', '')).toBe('Inbox · Louvre')
        expect(titleOf('Inbox', 'Acme Louvre')).toBe('Inbox · Acme Louvre')
        expect(titleOf(undefined, 'Acme Louvre')).toBe('Acme Louvre')
        expect(titleOf('', '  ')).toBe('Louvre')
    })
})
