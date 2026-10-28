// The server's API (louvre.web.api), its shapes as the server writes them, and the queries and writes the pages use.
//
// Every write carries X-Louvre: 1, which the server requires of a write, so a form on another site cannot make one.

import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query'

import type { Geometry, MapPlace } from '@/bridge/protocol'
import type { Anchor } from '@/bridge/text'

/** Who wrote a comment: a person, or an agent writing for one. */
export interface Author {
    /** Stable for the account's life. */
    id: string
    /** The name comments show. */
    display_name: string
    /** A person, or an agent. */
    kind: 'person' | 'agent'
    /** For an agent, the account id of the person it writes for. */
    on_behalf_of: string | null
    /** For an agent, the name of the person it writes for, when Louvre knows them. */
    on_behalf_of_name?: string | null
}

/** One comment in a thread. */
export interface Comment {
    /** Its id. */
    id: string
    /** Its thread's id. */
    thread_id: string
    /** Who wrote it. */
    author: Author
    /** Its text, empty once deleted. */
    body: string
    /** When it was written, as ISO 8601. */
    created_at: string
    /** When it was last edited, or null. */
    edited_at: string | null
    /** When it was deleted, or null. */
    deleted_at: string | null
    /** Whether it came from the web or an agent's tools. */
    via: 'web' | 'mcp'
}

/** A thread: the comments on a passage, or on the whole artifact. */
export interface Thread {
    /** Its id. */
    id: string
    /** The passage it is on, or null for the whole artifact; for a place on a map, the place's words. */
    anchor: Anchor | null
    /** The place on a map it is on, or null for words or the whole artifact. */
    place: ThreadPlace | null
    /** The version it was started on. */
    anchored_version: number
    /** Open, or resolved. */
    state: 'open' | 'resolved'
    /** Whether its passage is in the version asked about: null for a thread on the whole artifact. */
    anchor_status: 'found' | 'passage_gone' | null
    /** Its comments, oldest first. */
    comments: Comment[]
    /** Whether it has news for the signed-in person: a comment by another, or a resolving, since they last read it. */
    unread: boolean
}

/** A thread's place on a map, as the server keeps it: a feature by its layer and id, a point, or a box. */
export interface ThreadPlace {
    /** A feature, a point, or a box. */
    kind: 'feature' | 'point' | 'box'
    /** The feature's id; absent for a point or a box. */
    id?: string
    /** The feature's label when the thread was opened; absent for a point or a box. */
    label?: string
    /**
     * The feature's geometry, or the point's or the box's, as GeoJSON: a box's `bbox` is its west, south, east, and
     * north.
     */
    geometry: { type: string; coordinates?: unknown; bbox?: unknown } | null
    /** For a point read where its reader stood, how near the reading is sure to be, in metres; absent otherwise. */
    accuracy?: number
}

/** An artifact, as a list or its page shows it. */
export interface Artifact {
    /** Its id. */
    id: string
    /** Its latest version's title. */
    title: string
    /** The namespace it was published in. */
    namespace: string
    /** Where it came from: pairs such as canopy.ticket. */
    origin: Record<string, string>
    /** Its newest version's number. */
    latest_version: number
    /** When it was made. */
    created_at: string
}

/** An artifact in the list: with when it last changed, and how many threads are open. */
export interface Listed extends Artifact {
    /** When its latest version came. */
    updated_at: string
    /** How many of its threads are open. */
    open_threads: number
    /** How many of its decisions are open. */
    open_decisions: number
    /** How many of those ask the reader, who has not answered them. */
    awaiting: number
    /** Where a search's words were found in it; absent from a list that is not a search. */
    found?: Found
}

/** A run of a quote a search found: text, marked when it is one of the words searched for (louvre.core.search). */
export interface Hit {
    /** Its text. */
    text: string
    /** Set when it is a word searched for. */
    hit?: boolean
}

/** Where a search's words were found in an artifact. */
export interface Found {
    /** Its title, the words found marked. */
    title: Hit[]
    /** A few passages of its latest version holding them, in its order. */
    passages: Hit[][]
    /** A few comments holding them, those holding the most first. */
    comments: FoundComment[]
}

/** A comment a search found. */
export interface FoundComment {
    /** The thread it is in. */
    thread_id: string
    /** Its id. */
    comment_id: string
    /** Who wrote it. */
    author: Author
    /** Its words around the first found, the words found marked. */
    body: Hit[]
}

/** A version of an artifact. */
export interface Version {
    /** Its number, from 1. */
    n: number
    /** What it is written in. */
    content_type: 'text/html' | 'text/markdown' | 'application/geo+json'
    /** When it was published. */
    created_at: string
}

/** An artifact with its versions. */
export interface Detail {
    /** The artifact. */
    artifact: Artifact
    /** Its versions, oldest first. */
    versions: Version[]
    /** Whether the signed-in person owns it, and so may delete it. */
    owned: boolean
}

/** One passage that differs from an earlier version to a later one. */
export interface Change {
    /** Words added where there were none, removed leaving none, or rewritten as others. */
    kind: 'added' | 'removed' | 'changed'
    /** Finds it in the later version: its words, or the word beside where a removal's were; null for no text. */
    anchor: Anchor | null
    /** The words the later version has here, empty for a removal. */
    added: string
    /** The words the earlier version had here, empty for an addition. */
    removed: string
}

/** A feature a later version of a map added, removed, or moved, found in each by its id. */
export interface FeatureChange {
    /** What the later version did to it. */
    kind: 'added' | 'removed' | 'moved'
    /** Its id, as a place on the map names it. */
    id: string
    /** Its label: in the later version, or for one removed, in the earlier. */
    label: string
    /** Its geometry in the later version, or for one removed, in the earlier. */
    geometry: Geometry | null
    /** For one moved, its geometry in the earlier version; null otherwise. */
    was: Geometry | null
    /** For one moved, how far its middle moved, in whole metres: 0 for one reshaped where it was. */
    metres: number
    /** Which way it moved, such as "north-east"; empty when it did not. */
    toward: string
}

/** What became of a thread on the earlier version's text, in the later version. */
export interface ThreadFate {
    /** The thread's id. */
    thread_id: string
    /** Open, or resolved. */
    state: 'open' | 'resolved'
    /** Its passage untouched, a change in or beside it, or its words gone; null for a thread on the whole artifact. */
    outcome: 'unchanged' | 'near_change' | 'passage_gone' | null
}

/** What changed from one version of an artifact to a later one. */
export interface Comparison {
    /** The earlier version's number. */
    base: number
    /** The later version's number. */
    head: number
    /** The changes, in the later version's order. */
    changes: Change[]
    /** How many words the changes add. */
    words_added: number
    /** How many words the changes remove. */
    words_removed: number
    /** The features the later version of a map added, removed, or moved; none unless both versions are maps. */
    features: FeatureChange[]
    /** The threads on the earlier version's text, oldest first. */
    threads: ThreadFate[]
}

/** One choice a decision offers. */
export interface DecisionOption {
    /** Its id, such as o1, as answers name it. */
    id: string
    /** What it is, in a few words. */
    label: string
    /** A line more about it, or empty. */
    detail: string
    /** The passage of the artifact it is about, or null; for a place on its map, the place's words. */
    anchor: Anchor | null
    /** The place on the artifact's map it is about, or null. */
    place: ThreadPlace | null
    /** How many people chose it. */
    count: number
}

/** A person a decision asks, by login. */
export interface Asked {
    /** Their login. */
    login: string
    /** Their name, once they have signed in to Louvre; null before. */
    name: string | null
    /** Whether they have answered. */
    answered: boolean
}

/** A person's answer to a decision. */
export interface Answer {
    /** Their account's id. */
    account_id: string
    /** Their name. */
    name: string
    /** The options they chose. */
    choices: string[]
    /** What they added, or empty. */
    note: string
    /** When they last answered, as ISO 8601. */
    answered_at: string
}

/** A question asked on an artifact, for people to answer by choosing (ui/DESIGN.md, "Decisions"). */
export interface Decision {
    /** Its id. */
    id: string
    /** The artifact it is asked on. */
    artifact_id: string
    /** That artifact's title. */
    artifact_title: string
    /** What to decide. */
    question: string
    /** Whether an answer may choose more than one option. */
    multiple: boolean
    /** The artifact's version when it was asked. */
    version: number
    /** Its options, in order, each with how many chose it. */
    options: DecisionOption[]
    /** The people it asks. */
    asked: Asked[]
    /** Who asked it: an agent, or a person. */
    author: Author
    /** Open, or closed. */
    state: 'open' | 'closed'
    /** The option decided on when it was closed, or null. */
    outcome: string | null
    /** What its closer said, or empty. */
    outcome_note: string
    /** When it was asked, as ISO 8601. */
    created_at: string
    /** When it was closed, or null. */
    closed_at: string | null
    /** Every answer, oldest first. */
    answers: Answer[]
    /** What the reader chose, or null. */
    mine: { choices: string[]; note: string } | null
    /** Whether it asks the reader, who has not answered. */
    awaits_me: boolean
    /** Whether the reader may close it: they asked it, or their agent did. */
    may_close: boolean
}

/** Decisions, newest first, and how many open ones await the reader. */
export interface Decisions {
    /** The decisions. */
    decisions: Decision[]
    /** How many open decisions ask the reader, who has not answered. */
    awaiting: number
}

/** A board in the list: how many of its frames the reader reaches, and their artifacts' open threads. */
export interface ListedBoard {
    /** Its id. */
    id: string
    /** What it is called. */
    title: string
    /** Where its frames' artifacts are. */
    namespace: string
    /** How many of its frames the reader reaches. */
    frames: number
    /** How many threads are open on those frames' artifacts. */
    open_threads: number
}

/** One artifact on a board, at a screen's size and a place on the canvas, in CSS pixels. */
export interface BoardFrame {
    /** Unique on its board. */
    id: string
    /** What the board calls it beside its artifact's title, such as "Phone, 390". */
    label: string
    /** Its left edge on the canvas. */
    x: number
    /** Its top edge on the canvas. */
    y: number
    /** The width it is shown at, as a screen that wide would show it. */
    width: number
    /** The height it is shown at. */
    height: number
    /** The artifact it shows, at its latest version. */
    artifact: Listed
}

/** A board and the frames on it the reader reaches. */
export interface Board {
    /** The board. */
    board: { id: string; title: string; namespace: string }
    /** Its frames, in the order it lists them. */
    frames: BoardFrame[]
}

/** One page of the design study on its board, from the repository's pages: no artifact, nothing stored. */
export interface DirectionsFrame {
    /** Unique on the board. */
    id: string
    /** The direction's title. */
    title: string
    /** What the board calls it beside the title, such as "Phone, 390". */
    label: string
    /** Its left edge on the canvas. */
    x: number
    /** Its top edge on the canvas. */
    y: number
    /** The width it is shown at. */
    width: number
    /** The height it is shown at. */
    height: number
    /** The direction's page, as /directions serves it. */
    src: string
}

/** One change in an inbox: a comment another wrote, or a thread another resolved or reopened. */
export interface News {
    /** What changed. */
    kind: 'comment_created' | 'thread_resolved' | 'thread_reopened'
    /** Its place in the store's one sequence of changes. */
    seq: number
    /** When, as ISO 8601. */
    at: string
    /** The thread it is in. */
    thread_id: string
    /** The comment, for a comment. */
    comment_id: string | null
    /** The thread's passage, or null for a thread on the whole artifact. */
    passage: string | null
    /** The comment's text: null for a change that is no comment, or a comment since deleted. */
    body: string | null
    /** Who made it. */
    author: Author
}

/** An artifact in an inbox, with what is new on it. */
export interface InboxEntry {
    /** The artifact. */
    artifact: Artifact
    /** The newest version the person has opened, or null for none yet. */
    read_version: number | null
    /** How many changes to its threads are new. */
    unread: number
    /** How many of its threads have news. */
    threads: number
    /** When the newest news came, as ISO 8601. */
    at: string
    /** The newest few changes, newest first. */
    news: News[]
}

/** A signed-in person. */
export interface Account {
    /** Their id, such as gh:583231. */
    id: string
    /** Their handle. */
    login: string
    /** Their name, as comments show it. */
    name: string
}

/** A run of the owner's words: text, as a link or marked when the owner's Markdown said so (louvre.web.site). */
export interface Run {
    /** Its text; a newline in it breaks the line. */
    text: string
    /** Where it links to: the web, an address, or a page of Louvre's; absent for text. */
    href?: string
    /** Set in bold. */
    strong?: boolean
    /** Set in italics. */
    em?: boolean
    /** Set as code. */
    code?: boolean
}

/** What a deployment's owner says on its pages, each note as paragraphs of runs, none when it says nothing. */
export interface Site {
    /** What the deployment is called, in each page's title; empty for Louvre. */
    name: string
    /** Above the header of every page. */
    banner: Run[][]
    /** At the foot of the pages that list things, and of signing in. */
    footer: Run[][]
    /** Where a person signs in. */
    sign_in: Run[][]
    /** On the Tokens page. */
    tokens: Run[][]
}

/** Who is signed in, how one can sign in, and what the deployment's owner says on its pages. */
export interface Session {
    /** The signed-in person, or null. */
    account: Account | null
    /** Whether the deployment has its database. */
    configured: boolean
    /** Whether the demo is on, readable at /demo without signing in. */
    demo: boolean
    /** The ways to sign in. */
    sign_in: { github: boolean; dev: boolean }
    /** What the deployment's owner says on its pages. */
    site: Site
}

/** A token a person minted for an agent. */
export interface Token {
    /** Its id. */
    id: string
    /** The agent's name. */
    name: string
    /** The one namespace it reaches. */
    namespace: string
    /** What it may do. */
    scopes: ('read' | 'publish' | 'comment')[]
    /** When it was made, as ISO 8601. */
    created_at: string
    /** When an agent last used it, or null. */
    last_used_at: string | null
    /** When it was revoked, or null while it works. */
    revoked_at: string | null
}

/** A refusal: the server's code for why, and what it said. */
export class ApiError extends Error {
    /** The code, such as anchor_not_found. */
    readonly code: string
    /** The HTTP status. */
    readonly status: number

    /** Make the error the server answered with. */
    constructor(status: number, code: string, message: string) {
        super(message)
        this.name = 'ApiError'
        this.status = status
        this.code = code
    }
}

/** Ask the server, and read its JSON answer, or throw the refusal it gives. */
export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json' }
    if (method !== 'GET') {
        headers['X-Louvre'] = '1'
    }
    const init: RequestInit = { method, headers, credentials: 'same-origin' }
    if (body !== undefined) {
        headers['Content-Type'] = 'application/json'
        init.body = JSON.stringify(body)
    }
    const response = await fetch(path, init)
    if (response.status === 204) {
        return undefined as T
    }
    const data: unknown = await response.json().catch(() => null)
    if (!response.ok) {
        const said = (data ?? {}) as { code?: string; message?: string }
        throw new ApiError(response.status, said.code ?? 'error', said.message ?? response.statusText)
    }
    return data as T
}

/** How often an artifact's threads are read again while its page is open, in milliseconds. */
export const THREADS_POLL = 15_000

/** The session: who is signed in. */
export const sessionQuery = queryOptions({
    queryKey: ['session'],
    queryFn: () => request<Session>('GET', '/api/session'),
    staleTime: 60_000,
})

/** The namespace the demo publishes in (louvre.core.demo.NAMESPACE): a list leaves it out unless it names it. */
export const DEMO_NAMESPACE = 'demo'

/**
 * Read a page of the list of artifacts, newest first, from `cursor`, in `namespace` alone if given, and of those only
 * the ones whose origin holds every pair of `origin` if given, and that hold the words of `query` if given.
 */
export function listArtifacts(
    cursor: string | null,
    namespace?: string,
    origin?: Record<string, string>,
    query?: string,
) {
    const params = new URLSearchParams()
    if (cursor) {
        params.set('cursor', cursor)
    }
    if (namespace !== undefined) {
        params.set('namespace', namespace)
    }
    if (origin !== undefined) {
        // A JSON object, as the API takes it: an origin's key may hold any character.
        params.set('origin', JSON.stringify(origin))
    }
    if (query !== undefined) {
        params.set('q', query)
    }
    const search = params.size > 0 ? `?${params.toString()}` : ''
    return request<{ artifacts: Listed[]; next_cursor: string | null }>('GET', `/api/artifacts${search}`)
}

/** The boards the reader reaches a frame of, in `namespace` alone if given. */
export function boardsQuery(namespace?: string) {
    const query = namespace === undefined ? '' : `?${new URLSearchParams({ namespace }).toString()}`
    return queryOptions({
        queryKey: ['boards', namespace ?? null],
        queryFn: () => request<{ boards: ListedBoard[] }>('GET', `/api/boards${query}`),
    })
}

/** A board, with its frames. */
export function boardQuery(id: string) {
    return queryOptions({
        queryKey: ['board', id],
        queryFn: () => request<Board>('GET', `/api/boards/${encodeURIComponent(id)}`),
    })
}

/** The design study as a board, which needs no database. */
export const directionsBoardQuery = queryOptions({
    queryKey: ['directions-board'],
    queryFn: () =>
        request<{ board: { id: string; title: string; namespace: string }; frames: DirectionsFrame[] }>(
            'GET',
            '/api/directions/board',
        ),
})

/** An artifact and its versions. */
export function artifactQuery(id: string) {
    return queryOptions({
        queryKey: ['artifact', id],
        queryFn: () => request<Detail>('GET', `/api/artifacts/${encodeURIComponent(id)}`),
    })
}

/** An artifact's threads, each anchor looked for in `version`, and the `seq` to mark them read through. */
export function threadsQuery(id: string, version: number) {
    return queryOptions({
        queryKey: ['threads', id, version],
        queryFn: () =>
            request<{ threads: Thread[]; through: number | null }>(
                'GET',
                `/api/artifacts/${encodeURIComponent(id)}/threads?version=${String(version)}`,
            ),
        refetchInterval: THREADS_POLL,
    })
}

/** What changed from version `base` of an artifact to version `head`. */
export function compareQuery(id: string, base: number, head: number) {
    return queryOptions({
        queryKey: ['compare', id, base, head],
        queryFn: () =>
            request<Comparison>(
                'GET',
                `/api/artifacts/${encodeURIComponent(id)}/compare?base=${String(base)}&head=${String(head)}`,
            ),
        // Two published versions never change, so neither does what changed between them.
        staleTime: Infinity,
    })
}

/** How often the inbox is read again while a page is open, in milliseconds. */
export const INBOX_POLL = 60_000

/** What is new to the signed-in person, the newest first. */
export const inboxQuery = queryOptions({
    queryKey: ['inbox'],
    queryFn: () => request<{ entries: InboxEntry[] }>('GET', '/api/inbox'),
    refetchInterval: INBOX_POLL,
})

/** Mark an artifact read, or everything in the inbox; either reads the inbox again. */
export function useMarkRead() {
    const client = useQueryClient()
    const settle = () => client.invalidateQueries({ queryKey: ['inbox'] })
    return {
        artifact: useMutation({
            mutationFn: (given: { artifactId: string; version: number; through: number }) =>
                request('POST', `/api/artifacts/${encodeURIComponent(given.artifactId)}/read`, {
                    version: given.version,
                    through: given.through,
                }),
            onSettled: settle,
        }),
        all: useMutation({
            mutationFn: () => request('POST', '/api/inbox/read'),
            onSettled: settle,
        }),
    }
}

/** Every decision the reader reaches, newest first. */
export const decisionsQuery = queryOptions({
    queryKey: ['decisions', 'all'],
    queryFn: () => request<Decisions>('GET', '/api/decisions'),
    refetchInterval: THREADS_POLL,
})

/** An artifact's decisions, newest first. */
export function artifactDecisionsQuery(id: string) {
    return queryOptions({
        queryKey: ['decisions', 'artifact', id],
        queryFn: () => request<Decisions>('GET', `/api/artifacts/${encodeURIComponent(id)}/decisions`),
        refetchInterval: THREADS_POLL,
    })
}

/** The writes to decisions, each reading decisions and the list again once it is done. */
export function useDecisionWrites() {
    const client = useQueryClient()
    const settle = async () => {
        await client.invalidateQueries({ queryKey: ['decisions'] })
        await client.invalidateQueries({ queryKey: ['artifacts'] })
    }
    return {
        answer: useMutation({
            mutationFn: (given: { decisionId: string; choices: string[]; note: string }) =>
                request('POST', `/api/decisions/${encodeURIComponent(given.decisionId)}/answer`, {
                    choices: given.choices,
                    note: given.note,
                }),
            onSettled: settle,
        }),
        close: useMutation({
            mutationFn: (given: { decisionId: string; outcome: string | null; note: string }) =>
                request('POST', `/api/decisions/${encodeURIComponent(given.decisionId)}/close`, {
                    outcome: given.outcome,
                    note: given.note,
                }),
            onSettled: settle,
        }),
    }
}

/** The signed-in person's tokens. */
export const tokensQuery = queryOptions({
    queryKey: ['tokens'],
    queryFn: () => request<{ tokens: Token[] }>('GET', '/api/tokens'),
})

/** The writes to an artifact's threads, each reading the threads again once it is done. */
export function useThreadWrites(artifactId: string) {
    const client = useQueryClient()
    const settle = () => client.invalidateQueries({ queryKey: ['threads', artifactId] })
    const id = encodeURIComponent(artifactId)
    return {
        start: useMutation({
            mutationFn: (given: { anchor: Anchor | null; place: MapPlace | null; body: string }) =>
                request<{ thread_id: string }>('POST', `/api/artifacts/${id}/threads`, given),
            onSettled: settle,
        }),
        reply: useMutation({
            mutationFn: (given: { threadId: string; body: string }) =>
                request('POST', `/api/threads/${encodeURIComponent(given.threadId)}/replies`, { body: given.body }),
            onSettled: settle,
        }),
        resolve: useMutation({
            mutationFn: (given: { threadId: string; resolved: boolean }) =>
                request('POST', `/api/threads/${encodeURIComponent(given.threadId)}/resolve`, {
                    resolved: given.resolved,
                }),
            onSettled: settle,
        }),
        edit: useMutation({
            mutationFn: (given: { commentId: string; body: string }) =>
                request('PATCH', `/api/comments/${encodeURIComponent(given.commentId)}`, { body: given.body }),
            onSettled: settle,
        }),
        remove: useMutation({
            mutationFn: (commentId: string) => request('DELETE', `/api/comments/${encodeURIComponent(commentId)}`),
            onSettled: settle,
        }),
    }
}

/** Sign in by name, where the deployment allows it, or sign out; either reads the session again. */
export function useSignIn() {
    const client = useQueryClient()
    const settle = () => client.resetQueries()
    return {
        byName: useMutation({
            mutationFn: (login: string) => request('POST', '/auth/dev', { login }),
            onSuccess: settle,
        }),
        out: useMutation({
            mutationFn: () => request('POST', '/auth/sign-out'),
            onSuccess: settle,
        }),
    }
}
