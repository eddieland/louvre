import { cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { Words } from './site'

describe('the owner’s words', () => {
    afterEach(cleanup)

    it('draws markup as its text, never as elements', () => {
        const { container } = render(<Words paragraphs={[[{ text: '<script>alert(1)</script> <b>bold</b>' }]]} />)

        expect(container.querySelector('script, b')).toBeNull()
        expect(container.textContent).toBe('<script>alert(1)</script> <b>bold</b>')
    })

    it('sets each run as the owner marked it, a paragraph each', () => {
        const { container } = render(
            <Words
                paragraphs={[
                    [
                        { text: 'Ask in ' },
                        { text: '#louvre', strong: true },
                        { text: ', or ' },
                        { text: 'mail', em: true },
                    ],
                    [{ text: 'lvt_', code: true }, { text: ' tokens\nlast' }],
                ]}
            />,
        )

        const paragraphs = container.querySelectorAll('p')
        expect(paragraphs).toHaveLength(2)
        expect(paragraphs[0]?.innerHTML).toBe('Ask in <strong>#louvre</strong>, or <em>mail</em>')
        expect(paragraphs[1]?.innerHTML).toBe('<code>lvt_</code> tokens\nlast')
    })

    it('opens another site’s link in a tab of its own, and Louvre’s in place', () => {
        const { container } = render(
            <Words
                paragraphs={[
                    [
                        { text: 'policy', href: 'https://acme.test/policy', strong: true },
                        { text: ' ' },
                        { text: 'inbox', href: '/inbox' },
                    ],
                ]}
            />,
        )

        const [away, own] = container.querySelectorAll('a')
        expect(away?.getAttribute('href')).toBe('https://acme.test/policy')
        expect(away?.getAttribute('target')).toBe('_blank')
        expect(away?.getAttribute('rel')).toBe('noopener noreferrer')
        expect(away?.innerHTML).toBe('<strong>policy</strong>')
        expect(own?.getAttribute('href')).toBe('/inbox')
        expect(own?.hasAttribute('target')).toBe(false)
    })

    it('draws nothing when the owner says nothing', () => {
        const { container } = render(<Words paragraphs={[]} />)

        expect(container.innerHTML).toBe('')
    })
})
