// The theme: the reader's system's unless they pick one, which this browser remembers (ui/DESIGN.md, "Direction").

import { useSyncExternalStore } from 'react'

/** A theme. */
export type Theme = 'dark' | 'light'

const KEY = 'louvre:theme'
const DARK = '(prefers-color-scheme: dark)'
const listeners = new Set<() => void>()

/** Apply the theme this browser remembers, if any: once, before the first render. */
export function applyStoredTheme(): void {
    const stored = read()
    if (stored) {
        document.documentElement.dataset['theme'] = stored
    }
}

/** The theme shown now. */
export function currentTheme(): Theme {
    const set = document.documentElement.dataset['theme']
    if (set === 'dark' || set === 'light') {
        return set
    }
    return globalThis.matchMedia(DARK).matches ? 'dark' : 'light'
}

/** Show `theme`, and remember it in this browser. */
export function setTheme(theme: Theme): void {
    document.documentElement.dataset['theme'] = theme
    try {
        localStorage.setItem(KEY, theme)
    } catch {
        // Storage can be off (a private window); the theme still changes for this visit.
    }
    for (const listener of listeners) {
        listener()
    }
}

/** The theme shown now, kept current as it changes, here or in the system. */
export function useTheme(): Theme {
    return useSyncExternalStore(subscribe, currentTheme, () => 'dark')
}

function subscribe(listener: () => void): () => void {
    const media = globalThis.matchMedia(DARK)
    listeners.add(listener)
    media.addEventListener('change', listener)
    return () => {
        listeners.delete(listener)
        media.removeEventListener('change', listener)
    }
}

function read(): Theme | null {
    try {
        const stored = localStorage.getItem(KEY)
        return stored === 'dark' || stored === 'light' ? stored : null
    } catch {
        return null
    }
}
