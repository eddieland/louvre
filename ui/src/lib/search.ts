// What a catalogue's URL asks of it (ui/DESIGN.md, "Catalogue"), checked, as a URL is anyone's to write.

/** What a catalogue's URL asks of it. */
export interface CatalogueSearch {
    /** The origin pairs every artifact listed holds, such as its ticket. */
    origin?: Record<string, string>
}

/** Read a catalogue's search: an origin that is an object of strings, with a pair or more, or none at all. */
export function catalogueSearch(search: Record<string, unknown>): CatalogueSearch {
    const { origin } = search
    if (typeof origin !== 'object' || origin === null || Array.isArray(origin)) {
        return {}
    }
    const pairs: [string, string][] = []
    for (const [key, value] of Object.entries(origin)) {
        if (typeof value !== 'string') {
            return {}
        }
        pairs.push([key, value])
    }
    return pairs.length === 0 ? {} : { origin: Object.fromEntries(pairs) }
}
