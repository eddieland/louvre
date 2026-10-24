import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { useEffect, useEffectEvent, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react'

import type { FromBridge, Mark, Place, Selected } from '@/bridge/protocol'
import type { Anchor } from '@/bridge/text'
import { DecisionCard } from '@/components/decision'
import { Frame } from '@/components/frame'
import { Header } from '@/components/header'
import { Notice } from '@/components/notice'
import { ThreadNote } from '@/components/thread-note'
import type { Draft } from '@/components/thread-note'
import { SignInLink } from '@/components/sign-in'
import {
    ApiError,
    artifactDecisionsQuery,
    artifactQuery,
    boardQuery,
    request,
    sessionQuery,
    threadsQuery,
    useMarkRead,
    useThreadWrites,
} from '@/lib/api'
import type { Account, Decision, Detail, Thread } from '@/lib/api'
import { passageId, rank } from '@/lib/decisions'
import { ago, count, provenance, roman } from '@/lib/format'
import { clearSelection } from '@/lib/frame'
import { GAP, place } from '@/lib/layout'
import { useTheme } from '@/lib/theme'

/** At this width and below, the margin is a bottom sheet (ui/DESIGN.md, "Layout"). */
const NARROW = '(max-width: 960px)'
/** How long Undo stays offered after a thread is resolved, in milliseconds. */
const UNDO_MS = 5000

function isGone(thread: Thread): boolean {
    return thread.anchor_status === 'passage_gone'
}

/** Find a thread's note in the margin. */
function noteOf(rail: HTMLElement | null, id: string): HTMLElement | null {
    return (
        rail?.querySelector<HTMLElement>(
            `:scope > .thread[data-id="${CSS.escape(id)}"], .gone > .thread[data-id="${CSS.escape(id)}"]`,
        ) ?? null
    )
}

/** Which version the page shows, and the board frame it was opened from, if any. */
interface Search {
    /** The version, when it is not the latest. */
    v?: number
    /** The board it was opened from. */
    board?: string
    /** The frame on that board, whose width the page is shown at. */
    frame?: string
    /** A decision to open the page at, shown whole and scrolled to. */
    decision?: string
    /** The thread to open, as the inbox links to it. */
    t?: string
}

/** An artifact's page: a version in its frame, its threads in the margin (ui/DESIGN.md). */
export const Route = createFileRoute('/a/$artifactId')({
    validateSearch: (search: Record<string, unknown>): Search => {
        const v = Number(search['v'])
        const { board, frame, decision, t } = search
        return {
            ...(Number.isInteger(v) && v > 0 ? { v } : {}),
            ...(typeof board === 'string' && typeof frame === 'string' ? { board, frame } : {}),
            ...(typeof decision === 'string' ? { decision } : {}),
            ...(typeof t === 'string' && t ? { t } : {}),
        }
    },
    component: ArtifactPage,
})

function ArtifactPage() {
    const { artifactId } = Route.useParams()
    const detail = useQuery(artifactQuery(artifactId))
    const session = useQuery(sessionQuery)
    if (detail.error) {
        const missing = detail.error instanceof ApiError && detail.error.status === 404
        const signIn = detail.error instanceof ApiError && detail.error.status === 401
        return (
            <>
                <Header />
                <Notice title={missing ? 'No such artifact' : signIn ? 'Sign in to read this' : 'It did not load'}>
                    <p>{missing ? 'It may have been deleted, or the link is mistyped.' : detail.error.message}</p>
                    {signIn ? (
                        <SignInLink className="link">Sign in</SignInLink>
                    ) : (
                        <Link to="/" className="link">
                            Every artifact
                        </Link>
                    )}
                </Notice>
            </>
        )
    }
    if (!detail.data || !session.data) {
        return <Header />
    }
    return <Exhibit key={artifactId} detail={detail.data} account={session.data.account} />
}

function Exhibit({ detail, account }: { detail: Detail; account: Account | null }) {
    const { artifact, versions } = detail
    const search = Route.useSearch()
    const navigate = useNavigate()
    const version = Math.min(search.v ?? artifact.latest_version, artifact.latest_version)
    const latest = version === artifact.latest_version
    const shown = versions.find((v) => v.n === version)
    // Opened from a board's frame: shown at the frame's width, with the way back to the board.
    const framed =
        search.board !== undefined && search.frame !== undefined ? { board: search.board, frame: search.frame } : {}
    const board = useQuery({ ...boardQuery(search.board ?? ''), enabled: search.board !== undefined })
    const boardFrame = board.data?.frames.find((f) => f.id === search.frame && f.artifact.id === artifact.id)
    const threadsResult = useQuery(threadsQuery(artifact.id, version))
    const threads = threadsResult.data?.threads ?? []
    const writes = useThreadWrites(artifact.id)
    const { artifact: markRead } = useMarkRead()
    // Open decisions first, those awaiting the reader before the rest, each group newest first.
    const decisions = (useQuery(artifactDecisionsQuery(artifact.id)).data?.decisions ?? []).toSorted(
        (a, b) => rank(a) - rank(b),
    )
    const [toggled, setToggled] = useState<Record<string, boolean>>({})
    const shownWhole = (d: Decision) => toggled[d.id] ?? (d.state === 'open' || d.id === search.decision)
    const theme = useTheme()
    const narrow = useMedia(NARROW)

    const [active, setActive] = useState<string | null>(search.t ?? null)
    const [hover, setHover] = useState<string | null>(null)
    const [showResolved, setShowResolved] = useState(false)
    const [draft, setDraft] = useState<Draft | null>(null)
    const [places, setPlaces] = useState<Record<string, Place>>({})
    const [selection, setSelection] = useState<{ selected: Selected; top: number; left: number } | null>(null)
    const [toast, setToast] = useState<{ text: string; undo?: () => void } | null>(null)
    const [deleting, setDeleting] = useState(false)
    // The threads with news for the reader on this visit: kept once the page has marked them read, so they still say
    // so, and grown as news comes while the page is open.
    const [fresh, setFresh] = useState<ReadonlySet<string>>(new Set())

    const frameRef = useRef<HTMLIFrameElement>(null)
    const railRef = useRef<HTMLElement>(null)
    const goneRef = useRef<HTMLDivElement>(null)

    const signedIn = account !== null
    const writable = signedIn && latest

    // Which threads go where: on a passage in this version, on the whole page, or on a passage gone from it.
    const visible = (t: Thread) => t.state === 'open' || showResolved || t.id === active
    const anchored = threads.filter((t) => t.anchor && !isGone(t) && places[t.id] && visible(t))
    anchored.sort((a, b) => (places[a.id]?.top ?? 0) - (places[b.id]?.top ?? 0))
    const unplaced = threads.filter((t) => (!t.anchor || (!isGone(t) && !places[t.id])) && visible(t))
    const gone = threads.filter((t) => isGone(t) && visible(t))
    const numbers = new Map(anchored.map((t, i) => [t.id, i + 1]))
    const order = [...unplaced, ...anchored, ...gone].map((t) => t.id)
    const open = threads.filter((t) => t.state === 'open').length
    const goneOpen = threads.filter((t) => isGone(t) && t.state === 'open')
    const arrived = threads.filter((t) => t.unread && !fresh.has(t.id))
    if (arrived.length > 0) {
        setFresh(new Set([...fresh, ...arrived.map((t) => t.id)]))
    }
    const freshIds = threads.filter((t) => fresh.has(t.id)).map((t) => t.id)

    const marks: Mark[] = threads.flatMap((t): Mark[] =>
        t.anchor && !isGone(t) ? [{ id: t.id, anchor: t.anchor, state: t.state, n: numbers.get(t.id) ?? null }] : [],
    )
    if (draft?.anchor) {
        marks.push({ id: 'draft', anchor: draft.anchor, state: 'draft', n: null })
    }
    // Each option's passage, lit only while its option is hovered or shown.
    for (const d of decisions) {
        for (const o of d.options) {
            if (o.anchor) {
                marks.push({ id: passageId(d, o), anchor: o.anchor, state: 'passage', n: null })
            }
        }
    }

    const activate = (id: string | null) => {
        setActive(id)
        if (id !== 'draft') {
            setDraft(null)
        }
        const thread = threads.find((t) => t.id === id)
        if (thread?.state === 'resolved') {
            setShowResolved(true)
        }
    }

    const scrollToPassage = (id: string) => {
        const frame = frameRef.current
        const at = places[id]
        if (frame && at) {
            const top = frame.getBoundingClientRect().top + scrollY + at.top
            scrollTo({ top: Math.max(0, top - innerHeight / 3), behavior: 'smooth' })
        } else {
            noteOf(railRef.current, id)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
        }
    }

    const step = (delta: number) => {
        if (order.length === 0) {
            return
        }
        const at = active ? order.indexOf(active) : -1
        const next = at < 0 ? (delta > 0 ? 0 : order.length - 1) : (at + delta + order.length) % order.length
        const id = order[next]
        if (id) {
            activate(id)
            scrollToPassage(id)
        }
    }

    // To the next thread with news after the active one, open or resolved, in the order they were started.
    const nextFresh = () => {
        const id = freshIds[(freshIds.indexOf(active ?? '') + 1) % freshIds.length]
        if (id) {
            activate(id)
            scrollToPassage(id)
        }
    }

    const startDraft = (anchor: Anchor | null) => {
        if (!writable) {
            return
        }
        setDraft({ id: 'draft', anchor, state: 'draft' })
        setActive('draft')
        setSelection(null)
    }

    const close = () => {
        setDraft(null)
        setActive(null)
    }

    const onKey = (key: string) => {
        if (key === 'Escape') {
            close()
        } else if (key === 'c' && selection?.selected.anchor) {
            startDraft(selection.selected.anchor)
        } else if (key === 'j') {
            step(1)
        } else if (key === 'k') {
            step(-1)
        }
    }

    const onBridge = (message: FromBridge) => {
        switch (message.type) {
            case 'ready': {
                break
            }
            case 'layout': {
                if (JSON.stringify(message.places) !== JSON.stringify(places)) {
                    setPlaces(message.places)
                }
                break
            }
            case 'selection': {
                setSelection(message.selected ? { selected: message.selected, ...addAt(message.selected) } : null)
                break
            }
            case 'click': {
                if (message.id) {
                    activate(message.id)
                } else if (active !== 'draft') {
                    setActive(null)
                }
                break
            }
            case 'hover': {
                setHover(message.id)
                break
            }
            case 'key': {
                onKey(message.key)
                break
            }
            default: {
                message satisfies never
            }
        }
    }

    // Where "comment" sits for a selection: in the margin level with it, or above it on a narrow screen.
    const addAt = (selected: Selected) => {
        const frame = frameRef.current?.getBoundingClientRect()
        const rail = railRef.current?.getBoundingClientRect()
        const top = (frame?.top ?? 0) + scrollY + selected.top
        if (narrow || !rail) {
            const middle = (frame?.left ?? 0) + (selected.left + selected.right) / 2
            return { top: top - 36, left: Math.max(16, Math.min(middle - 40, innerWidth - 120)) }
        }
        return { top, left: rail.left + scrollX }
    }

    const onWindowKey = useEffectEvent((event: KeyboardEvent) => {
        const target = event.target instanceof Element ? event.target : null
        const typing = target?.closest('input, textarea, select') !== null && target !== null
        const chord = event.metaKey || event.ctrlKey || event.altKey
        // Escape closes a thread from anywhere but a field, which handles its own; the letters only off a control.
        const control = target?.closest('button, a') !== null && target !== null
        if (typing || chord || (control && event.key !== 'Escape')) {
            return
        }
        if (['j', 'k', 'c', 'Escape'].includes(event.key)) {
            onKey(event.key)
        }
    })
    useEffect(() => {
        const listener = (event: KeyboardEvent) => onWindowKey(event)
        globalThis.addEventListener('keydown', listener)
        return () => globalThis.removeEventListener('keydown', listener)
    }, [])

    useEffect(() => {
        if (!toast) {
            return
        }
        const timer = setTimeout(() => setToast(null), UNDO_MS)
        return () => clearTimeout(timer)
    }, [toast])

    useEffect(() => {
        document.title = `${artifact.title} · Louvre`
    }, [artifact.title])

    // Opened at a decision, from the list of decisions or an agent's link: scroll to it once it has loaded.
    const scrolledTo = useRef<string | null>(null)
    const wanted = decisions.some((d) => d.id === search.decision) ? search.decision : undefined
    useEffect(() => {
        if (wanted && scrolledTo.current !== wanted) {
            scrolledTo.current = wanted
            document.querySelector(`#decision-${CSS.escape(wanted)}`)?.scrollIntoView({ block: 'start' })
        }
    }, [wanted])

    // Opened at a thread, as the inbox links to one: once its passage is placed, it is scrolled to.
    const jumped = useRef(false)
    const jump = useEffectEvent(() => {
        const id = search.t
        const thread = threads.find((t) => t.id === id)
        if (jumped.current || !id || !thread || (thread.anchor && !isGone(thread) && !places[id])) {
            return
        }
        jumped.current = true
        activate(id)
        scrollToPassage(id)
    })
    useEffect(() => jump())

    // The reader has seen the threads as they were read: the page marks the artifact read through them.
    const through = threadsResult.data?.through ?? null
    const marked = useRef('')
    const mark = useEffectEvent(() => {
        const key = `${String(version)}:${String(through)}`
        if (!signedIn || through === null || marked.current === key) {
            return
        }
        marked.current = key
        markRead.mutate({ artifactId: artifact.id, version, through })
    })
    useEffect(() => mark())

    useEffect(() => {
        document.body.classList.toggle('sheet-open', narrow && active !== null)
        return () => document.body.classList.remove('sheet-open')
    }, [narrow, active])

    // The margin, placed by hand after every render: each thread level with its passage, moved aside to fit.
    const draftTop = (offset: number) => {
        const at = places['draft']
        return draft?.anchor && at ? offset + at.top : 0
    }
    const layout = useEffectEvent(() => {
        const rail = railRef.current
        const frame = frameRef.current
        if (!rail || !frame) {
            return
        }
        const all = [...rail.querySelectorAll<HTMLElement>(':scope > .thread')]
        if (narrow) {
            for (const node of all) {
                node.style.top = ''
            }
            rail.style.minHeight = ''
            if (goneRef.current) {
                goneRef.current.style.top = ''
            }
            return
        }
        const offset = frame.getBoundingClientRect().top - rail.getBoundingClientRect().top
        const items = [...unplaced, ...anchored, ...(draft ? [draft] : [])].flatMap((t) => {
            const node = noteOf(rail, t.id)
            const want = t.id === 'draft' ? draftTop(offset) : t.anchor ? offset + (places[t.id]?.top ?? 0) : 0
            return node ? [{ id: t.id, node, want, height: node.offsetHeight }] : []
        })
        items.sort((a, b) => a.want - b.want)
        const tops = place(items, active)
        items.forEach((item, i) => {
            item.node.style.top = `${tops[i] ?? 0}px`
        })
        const last = items.at(-1)
        const end = last ? (tops.at(-1) ?? 0) + last.height + 4 * GAP : 0
        const goneHeight = goneRef.current?.offsetHeight ?? 0
        if (goneRef.current) {
            goneRef.current.style.top = `${end}px`
        }
        rail.style.minHeight = `${end + goneHeight + GAP}px`
    })
    useLayoutEffect(() => layout())
    useEffect(() => {
        const observer = new ResizeObserver(() => layout())
        for (const node of railRef.current?.querySelectorAll('.thread') ?? []) {
            observer.observe(node)
        }
        const listener = () => {
            setSelection(null)
            layout()
        }
        globalThis.addEventListener('resize', listener)
        return () => {
            observer.disconnect()
            globalThis.removeEventListener('resize', listener)
        }
    })

    const resolve = (thread: Thread, resolved: boolean) => {
        writes.resolve.mutate({ threadId: thread.id, resolved })
        if (resolved) {
            if (active === thread.id) {
                setActive(null)
            }
            setToast({
                text: 'Thread resolved',
                undo: () => writes.resolve.mutate({ threadId: thread.id, resolved: false }),
            })
        }
    }

    const note = (thread: Thread | Draft) => {
        const id = thread.id
        return (
            <ThreadNote
                key={id}
                thread={thread}
                n={numbers.get(id) ?? null}
                active={active === id}
                hovered={hover === id}
                fresh={fresh.has(id)}
                gone={thread.state !== 'draft' && isGone(thread)}
                version={version}
                account={account}
                writable={writable}
                onActivate={() => activate(id)}
                onHover={(on) => setHover(on ? id : null)}
                onClose={close}
                onReply={async (body) => {
                    if (thread.state === 'draft') {
                        const made = await writes.start.mutateAsync({ anchor: thread.anchor, body })
                        clearSelection(frameRef.current)
                        setDraft(null)
                        setActive(made.thread_id)
                        return
                    }
                    await writes.reply.mutateAsync({ threadId: id, body })
                }}
                onResolve={(resolved) => {
                    if (thread.state !== 'draft') {
                        resolve(thread, resolved)
                    }
                }}
                onEdit={(commentId, body) => writes.edit.mutateAsync({ commentId, body })}
                onDelete={(commentId) => writes.remove.mutate(commentId)}
            />
        )
    }

    const from = provenance(artifact.origin)
    const kind = { 'text/html': 'HTML', 'text/markdown': 'Markdown', 'application/geo+json': 'GeoJSON' }[
        shown?.content_type ?? 'text/html'
    ]
    const activeThread = threads.find((t) => t.id === active)
    return (
        <>
            <Header
                provenance={
                    <>
                        <span className="long">{artifact.namespace} &middot; </span>
                        <b>{from ?? artifact.title}</b>
                    </>
                }
            />
            <nav className="toolbar" aria-label="Versions and threads">
                <div className="versions">
                    {board.data && boardFrame ? (
                        <Link
                            to="/b/$boardId"
                            params={{ boardId: board.data.board.id }}
                            className="pill back"
                            aria-label={`Back to ${board.data.board.title}`}
                        >
                            &larr; <span className="long">{board.data.board.title}</span>
                            <span className="short">Board</span>
                        </Link>
                    ) : null}
                    <span className="label long">Version</span>
                    {versions.map((v) => (
                        <Link
                            key={v.n}
                            to="/a/$artifactId"
                            params={{ artifactId: artifact.id }}
                            search={{ ...(v.n === artifact.latest_version ? {} : { v: v.n }), ...framed }}
                            className="pill"
                            data-current={v.n === version ? '' : undefined}
                            activeOptions={{ includeSearch: true }}
                            aria-label={`Version ${v.n}`}
                        >
                            {roman(v.n)}
                        </Link>
                    ))}
                </div>
                <div className="toolbar-right">
                    {freshIds.length > 0 ? (
                        <button type="button" className="pill text-accent" onClick={nextFresh}>
                            {freshIds.length} new
                        </button>
                    ) : null}
                    {goneOpen.length > 0 ? (
                        <button
                            type="button"
                            className="pill text-accent"
                            onClick={() => {
                                const first = goneOpen[0]
                                if (first) {
                                    activate(first.id)
                                    noteOf(railRef.current, first.id)?.scrollIntoView({
                                        block: 'center',
                                        behavior: 'smooth',
                                    })
                                }
                            }}
                        >
                            <span className="long">{count(goneOpen.length, 'note')} on passages since removed</span>
                            <span className="short">{goneOpen.length} removed</span>
                        </button>
                    ) : null}
                    {writable ? (
                        <button type="button" className="pill" onClick={() => startDraft(null)}>
                            <span className="long">Comment on the page</span>
                            <span className="short">Comment</span>
                        </button>
                    ) : null}
                    <div className="filters">
                        <button
                            type="button"
                            className="pill"
                            aria-pressed={!showResolved}
                            onClick={() => {
                                setShowResolved(false)
                                if (narrow && active === null) {
                                    step(1)
                                }
                            }}
                        >
                            Open <span className="tabular-nums">{open}</span>
                        </button>
                        <button
                            type="button"
                            className="pill"
                            aria-pressed={showResolved}
                            onClick={() => setShowResolved(true)}
                        >
                            All
                        </button>
                    </div>
                </div>
            </nav>
            {latest ? null : (
                <p className="older">
                    This is version {roman(version)}. Comments go on the latest,{' '}
                    <Link to="/a/$artifactId" params={{ artifactId: artifact.id }} search={framed} className="link">
                        version {roman(artifact.latest_version)}
                    </Link>
                    .
                </p>
            )}
            {decisions.length > 0 ? (
                <section className="decisions" aria-label="Decisions">
                    {decisions.map((d) => (
                        <DecisionCard
                            key={d.id}
                            decision={d}
                            account={account}
                            open={shownWhole(d)}
                            onToggle={() => setToggled({ ...toggled, [d.id]: !shownWhole(d) })}
                            onLight={(o) => setHover(o ? passageId(d, o) : null)}
                            onShow={(o) => {
                                setHover(passageId(d, o))
                                scrollToPassage(passageId(d, o))
                            }}
                        />
                    ))}
                </section>
            ) : null}
            <main className="stage" data-framed={boardFrame ? '' : undefined}>
                <div
                    className="sheet"
                    style={boardFrame ? { maxWidth: `${String(boardFrame.width + 2)}px` } : undefined}
                >
                    <p className="label">
                        <span>
                            {artifact.title} &middot; {boardFrame ? boardFrame.label : kind}
                        </span>
                        <span>{shown ? `Published ${ago(shown.created_at)}` : null}</span>
                    </p>
                    <Frame
                        key={version}
                        src={`/content/${encodeURIComponent(artifact.id)}/${version}`}
                        title={artifact.title}
                        marks={marks}
                        active={active}
                        hover={hover}
                        theme={theme}
                        frameRef={frameRef}
                        onMessage={onBridge}
                    />
                </div>
                <aside ref={railRef} className="rail" aria-label="Comments">
                    {narrow ? (
                        <div className="sheet-head">
                            <span className="label">{activeThread || draft ? 'Comments' : ''}</span>
                            <button type="button" className="action" onClick={close}>
                                Close
                            </button>
                        </div>
                    ) : null}
                    {threads.length === 0 && !draft && !narrow ? (
                        <p className="rail-empty">
                            {writable
                                ? 'No comments yet. Select words in the page to comment on them.'
                                : 'No comments yet.'}
                        </p>
                    ) : null}
                    {[...unplaced, ...anchored].map((t) => note(t))}
                    {draft ? note(draft) : null}
                    <div ref={goneRef} className="gone">
                        {gone.length > 0 ? <p className="gone-title">Not in this version</p> : null}
                        {gone.map((t) => note(t))}
                    </div>
                </aside>
            </main>
            {detail.owned ? (
                <footer className="mx-auto max-w-295 px-5 pb-16 sm:px-8">
                    {deleting ? (
                        <p className="font-ui text-sm">
                            Delete this artifact and its threads for everyone?{' '}
                            <button
                                type="button"
                                className="action action-primary"
                                onClick={() => {
                                    void request('DELETE', `/api/artifacts/${encodeURIComponent(artifact.id)}`).then(
                                        () => navigate({ to: '/' }),
                                    )
                                }}
                            >
                                Delete
                            </button>{' '}
                            <button type="button" className="action" onClick={() => setDeleting(false)}>
                                Keep it
                            </button>
                        </p>
                    ) : (
                        <button type="button" className="action" onClick={() => setDeleting(true)}>
                            Delete this artifact
                        </button>
                    )}
                </footer>
            ) : null}
            {selection && writable && !draft ? (
                <button
                    type="button"
                    className="add"
                    style={{ top: `${selection.top}px`, left: `${selection.left}px` }}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => {
                        if (selection.selected.anchor) {
                            startDraft(selection.selected.anchor)
                        } else {
                            setToast({ text: 'That passage is too long to comment on; select less.' })
                        }
                    }}
                >
                    comment
                </button>
            ) : null}
            {toast ? (
                <output className="toast">
                    <span>{toast.text}</span>
                    {toast.undo ? (
                        <button
                            type="button"
                            className="action action-primary"
                            onClick={() => {
                                toast.undo?.()
                                setToast(null)
                            }}
                        >
                            Undo
                        </button>
                    ) : null}
                </output>
            ) : null}
        </>
    )
}

/** Whether a media query matches, kept current. */
function useMedia(query: string): boolean {
    return useSyncExternalStore(
        (listener) => {
            const media = globalThis.matchMedia(query)
            media.addEventListener('change', listener)
            return () => media.removeEventListener('change', listener)
        },
        () => globalThis.matchMedia(query).matches,
        () => false,
    )
}
