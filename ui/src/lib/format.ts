// How Louvre writes times, version numbers, and where an artifact came from.

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
    ['year', 365 * 24 * 3600],
    ['month', 30 * 24 * 3600],
    ['week', 7 * 24 * 3600],
    ['day', 24 * 3600],
    ['hour', 3600],
    ['minute', 60],
]
const RELATIVE = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

/** Say how long ago an ISO 8601 time was, such as "3 hours ago", or "just now" within a minute. */
export function ago(iso: string, now: number = Date.now()): string {
    const seconds = Math.round((Date.parse(iso) - now) / 1000)
    for (const [unit, size] of UNITS) {
        if (Math.abs(seconds) >= size) {
            return RELATIVE.format(Math.trunc(seconds / size), unit)
        }
    }
    return 'just now'
}

const NUMERALS: [number, string][] = [
    [1000, 'M'],
    [900, 'CM'],
    [500, 'D'],
    [400, 'CD'],
    [100, 'C'],
    [90, 'XC'],
    [50, 'L'],
    [40, 'XL'],
    [10, 'X'],
    [9, 'IX'],
    [5, 'V'],
    [4, 'IV'],
    [1, 'I'],
]

/** Write a version's number in roman numerals, as its pill shows it (ui/DESIGN.md, "Chrome"). */
export function roman(n: number): string {
    let left = n
    let out = ''
    for (const [value, numeral] of NUMERALS) {
        while (left >= value) {
            out += numeral
            left -= value
        }
    }
    return out || String(n)
}

/** The origin keys that name where an artifact came from, the most telling first. */
const ORIGIN_KEYS = ['canopy.ticket', 'ticket', 'canopy.report', 'canopy.repo']

/** Name where an artifact came from by its origin: its ticket, say, or null when its origin is empty. */
export function provenance(origin: Record<string, string>): string | null {
    const key = ORIGIN_KEYS.find((k) => origin[k]) ?? Object.keys(origin).toSorted()[0]
    return key === undefined ? null : (origin[key] ?? null)
}

/** Say how many of a thing there are, as "1 thread" or "3 threads". */
export function count(n: number, one: string, many = `${one}s`): string {
    return `${n} ${n === 1 ? one : many}`
}
