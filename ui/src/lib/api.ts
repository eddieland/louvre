// The server's API (louvre.web.api), its shapes as the server writes them, and the queries and writes the pages use.
//
// Every write carries X-Louvre: 1, which the server requires of a write, so a form on another site cannot make one.

import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query'

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
    /** The passage it is on, or null for the whole artifact. */
    anchor: Anchor | null
    /** The version it was started on. */
    anchored_version: number
    /** Open, or resolved. */
    state: 'open' | 'resolved'
    /** Whether its passage is in the version asked about: null for a thread on the whole artifact. */
    anchor_status: 'found' | 'passage_gone' | null
    /** Its comments, oldest first. */
    comments: Comment[]
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
}

/** A version of an artifact. */
export interface Version {
    /** Its number, from 1. */
    n: number
    /** What it is written in. */
    content_type: 'text/html' | 'text/markdown'
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

/** A signed-in person. */
export interface Account {
    /** Their id, such as gh:583231. */
    id: string
    /** Their handle. */
    login: string
    /** Their name, as comments show it. */
    name: string
}

/** Who is signed in, and how one can sign in. */
export interface Session {
    /** The signed-in person, or null. */
    account: Account | null
    /** Whether the deployment has its database. */
    configured: boolean
    /** Whether the demo is on, readable without signing in. */
    demo: boolean
    /** The ways to sign in. */
    sign_in: { github: boolean; dev: boolean }
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

/** Read a page of the list of artifacts, newest first, from `cursor`. */
export function listArtifacts(cursor: string | null) {
    const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''
    return request<{ artifacts: Listed[]; next_cursor: string | null }>('GET', `/api/artifacts${query}`)
}

/** The boards the reader reaches a frame of. */
export const boardsQuery = queryOptions({
    queryKey: ['boards'],
    queryFn: () => request<{ boards: ListedBoard[] }>('GET', '/api/boards'),
})

/** A board, with its frames. */
export function boardQuery(id: string) {
    return queryOptions({
        queryKey: ['board', id],
        queryFn: () => request<Board>('GET', `/api/boards/${encodeURIComponent(id)}`),
    })
}

/** An artifact and its versions. */
export function artifactQuery(id: string) {
    return queryOptions({
        queryKey: ['artifact', id],
        queryFn: () => request<Detail>('GET', `/api/artifacts/${encodeURIComponent(id)}`),
    })
}

/** An artifact's threads, each anchor looked for in `version`. */
export function threadsQuery(id: string, version: number) {
    return queryOptions({
        queryKey: ['threads', id, version],
        queryFn: () =>
            request<{ threads: Thread[] }>(
                'GET',
                `/api/artifacts/${encodeURIComponent(id)}/threads?version=${String(version)}`,
            ),
        refetchInterval: THREADS_POLL,
    })
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
            mutationFn: (given: { anchor: Anchor | null; body: string }) =>
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
