import { describe, expect, it } from 'vitest'

import { localPath } from './paths'

describe('localPath', () => {
    it('keeps a page of Louvre’s own, with its query', () => {
        expect(localPath('/a/report-1?version=2')).toBe('/a/report-1?version=2')
        expect(localPath('/')).toBe('/')
    })

    it('never leads off Louvre or back into /auth', () => {
        for (const given of [
            'https://evil.test/',
            '//evil.test/',
            '/\\evil.test/',
            '/\t/evil.test',
            'a/b',
            '/auth/github',
        ]) {
            expect(localPath(given)).toBe('/')
        }
        expect(localPath(undefined)).toBe('/')
    })
})
