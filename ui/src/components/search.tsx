import { useNavigate } from '@tanstack/react-router'
import { useEffect, useEffectEvent, useRef } from 'react'

import type { Found, Hit } from '@/lib/api'
import { MAX_QUERY } from '@/lib/search'

/** What the search field searches: the words it holds, and the origin the list is filtered by, which it keeps. */
export interface SearchFieldProps {
    /** The words searched for now, if any. */
    query?: string
    /** The origin pairs the list is filtered by, kept by a search. */
    origin?: Record<string, string>
}

/**
 * The catalogue's search: one line that searches on Enter, its words in the page's URL (ui/DESIGN.md, "Catalogue").
 * `/` anywhere on the page but a field puts the cursor in it.
 */
export function SearchField({ query, origin }: SearchFieldProps) {
    const navigate = useNavigate()
    const field = useRef<HTMLInputElement>(null)
    const onWindowKey = useEffectEvent((event: KeyboardEvent) => {
        const target = event.target instanceof Element ? event.target : null
        const typing = target !== null && target.closest('input, textarea, select, [contenteditable]') !== null
        if (event.key !== '/' || typing || event.metaKey || event.ctrlKey || event.altKey) {
            return
        }
        event.preventDefault()
        field.current?.focus()
    })
    useEffect(() => {
        const listener = (event: KeyboardEvent) => onWindowKey(event)
        globalThis.addEventListener('keydown', listener)
        return () => globalThis.removeEventListener('keydown', listener)
    }, [])
    return (
        <search className="search">
            <form
                onSubmit={(event) => {
                    event.preventDefault()
                    const q = field.current?.value.trim() ?? ''
                    void navigate({
                        to: '.',
                        search: { ...(origin === undefined ? {} : { origin }), ...(q === '' ? {} : { q }) },
                    })
                }}
            >
                <input
                    // A new search, or leaving one, sets the field to the URL's words.
                    key={query ?? ''}
                    ref={field}
                    type="search"
                    name="q"
                    className="field search-field"
                    defaultValue={query}
                    maxLength={MAX_QUERY}
                    placeholder="Search"
                    aria-label="Search titles, pages, and comments"
                    enterKeyHint="search"
                />
            </form>
        </search>
    )
}

/** A quote a search found, the words searched for marked on the passage's band. */
export function Marked({ runs }: { runs: Hit[] }) {
    return runs.map((run, i) =>
        run.hit ? (
            // oxlint-disable-next-line react/no-array-index-key -- a quote's runs never move.
            <mark key={i} className="hit">
                {run.text}
            </mark>
        ) : (
            // oxlint-disable-next-line react/no-array-index-key -- a quote's runs never move.
            <span key={i}>{run.text}</span>
        ),
    )
}

/** Where a search found its words in an artifact, under its entry: its passages, then its comments. */
export function FoundLines({ found }: { found: Found }) {
    if (found.passages.length === 0 && found.comments.length === 0) {
        return null
    }
    return (
        <span className="news">
            {found.passages.map((passage, i) => (
                // oxlint-disable-next-line react/no-array-index-key -- the passages are in the page's order, and stay.
                <span key={i} className="news-item found-passage">
                    <Marked runs={passage} />
                </span>
            ))}
            {found.comments.map((comment) => (
                <span key={comment.comment_id} className="news-item">
                    <span className="news-line">
                        <span className="who">{comment.author.display_name}</span>
                        {comment.author.kind === 'agent' ? (
                            <em className="agent-badge">
                                (Agent
                                {comment.author.on_behalf_of_name ? `, for ${comment.author.on_behalf_of_name}` : ''})
                            </em>
                        ) : null}{' '}
                        <Marked runs={comment.body} />
                    </span>
                </span>
            ))}
        </span>
    )
}
