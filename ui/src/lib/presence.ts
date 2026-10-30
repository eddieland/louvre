import type { Present } from '@/lib/api'

/** The most agents the presence line names; the rest it counts. */
export const MOST_NAMED = 3

/** What each activity is said as, after the agent's name; replying names its thread where it can. */
const DOING: Record<Present['activity'], string> = {
    here: 'is here',
    reading: 'is reading',
    revising: 'is revising this page',
    replying: 'is replying',
}

/** Say what an agent present on an artifact is doing, after its name: `is revising this page`. */
export function doing(present: Present, numberOf: (threadId: string) => number | null): string {
    const n = present.activity === 'replying' && present.thread_id !== null ? numberOf(present.thread_id) : null
    return n === null ? DOING[present.activity] : `is replying in thread ${String(n)}`
}

/** The names of the agents replying in a thread, as its note in the margin says they are. */
export function replyingIn(present: readonly Present[], threadId: string): string[] {
    return present
        .filter((p) => p.activity === 'replying' && p.thread_id === threadId)
        .map((p) => p.author.display_name)
}

/** Split the agents present into those the line names and how many more it counts. */
export function named(present: readonly Present[]): { shown: Present[]; more: number } {
    return { shown: present.slice(0, MOST_NAMED), more: Math.max(0, present.length - MOST_NAMED) }
}
