// What a catalogue's URL asks of it (ui/DESIGN.md, "Catalogue"), checked, as a URL is anyone's to write.

/** The most characters a search may hold, as the API takes it (louvre.core.search.MAX_QUERY). */
export const MAX_QUERY = 200

/** What a catalogue's URL asks of it. */
export interface CatalogueSearch {
    /** The origin pairs every artifact listed holds, such as its ticket. */
    origin?: Record<string, string>
    /** The words every artifact listed holds, in its title, its words, or its comments. */
    q?: string
}

/**
 * Read a catalogue's search: an origin that is an object of strings, with a pair or more, or none at all; and words
 * to search for, none when blank or past the most a search holds.
 */
export function catalogueSearch(search: Record<string, unknown>): CatalogueSearch {
    const origin = originOf(search.origin)
    const q = typeof search.q === 'string' ? search.q.trim() : ''
    return {
        ...(origin === undefined ? {} : { origin }),
        ...(q === '' || q.length > MAX_QUERY ? {} : { q }),
    }
}

function originOf(origin: unknown): Record<string, string> | undefined {
    if (typeof origin !== 'object' || origin === null || Array.isArray(origin)) {
        return undefined
    }
    const pairs: [string, string][] = []
    for (const [key, value] of Object.entries(origin)) {
        if (typeof value !== 'string') {
            return undefined
        }
        pairs.push([key, value])
    }
    return pairs.length === 0 ? undefined : Object.fromEntries(pairs)
}
