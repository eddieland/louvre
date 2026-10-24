import { useState } from 'react'

import { Composer } from '@/components/composer'
import { SignInLink } from '@/components/sign-in'
import type { Account, Comment, Thread } from '@/lib/api'
import { ago, roman } from '@/lib/format'

/** A thread as the margin shows it, and what the reader can do with it. */
export interface ThreadNoteProps {
    /** The thread, or a draft's (no id on the server yet, no comments). */
    thread: Thread | Draft
    /** Its number in the margin, or null. */
    n: number | null
    /** Whether it is the active thread. */
    active: boolean
    /** Whether it or its passage is hovered. */
    hovered: boolean
    /** Whether its passage is gone from the version shown. */
    gone: boolean
    /** The version shown. */
    version: number
    /** The signed-in person, who may reply, or null for a reader who may not. */
    account: Account | null
    /** Whether new comments may be made here: false while an older version is shown. */
    writable: boolean
    /** Make it the active thread. */
    onActivate: () => void
    /** The pointer came onto it, or left it. */
    onHover: (on: boolean) => void
    /** Close it, or drop the draft. */
    onClose: () => void
    /** Send a reply, or a draft's first comment. */
    onReply: (body: string) => Promise<unknown>
    /** Resolve it, or reopen it. */
    onResolve: (resolved: boolean) => void
    /** Change a comment of the reader's own. */
    onEdit: (commentId: string, body: string) => Promise<unknown>
    /** Delete a comment of the reader's own. */
    onDelete: (commentId: string) => void
}

/** A thread not yet sent: its passage, and the composer for its first comment. */
export interface Draft {
    /** Always `draft`. */
    id: 'draft'
    /** The passage, or null for the whole artifact. */
    anchor: Thread['anchor']
    /** Always `draft`. */
    state: 'draft'
}

/**
 * One thread in the margin: no box, the author's name in small caps, then the text inline; an agent's comment says
 * whose agent it is (ui/DESIGN.md, "Threads").
 */
export function ThreadNote(props: ThreadNoteProps) {
    const { thread, n, active, hovered } = props
    const draft = thread.state === 'draft'
    const classes = ['thread', active ? 'is-active' : '', hovered ? 'is-hover' : ''].filter(Boolean).join(' ')
    return (
        // oxlint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- hover only lights the passage
        <section
            className={classes}
            data-id={thread.id}
            data-state={thread.state}
            aria-label={draft ? 'New comment' : `Thread${n === null ? '' : ` ${n}`}`}
            onMouseEnter={() => props.onHover(true)}
            onMouseLeave={() => props.onHover(false)}
        >
            {n === null ? null : <span className="thread-n">{n}</span>}
            {active || draft ? (
                <Body {...props} />
            ) : (
                <button type="button" className="thread-open" onClick={props.onActivate}>
                    <Body {...props} />
                </button>
            )}
        </section>
    )
}

function Body(props: ThreadNoteProps) {
    const { thread, active, gone, version, account, writable } = props
    if (thread.state === 'draft') {
        return <DraftBody {...props} />
    }
    return (
        <>
            {gone ? (
                <>
                    <span className="gone-note">
                        On version {roman(thread.anchored_version)}. The passage is not in version {roman(version)}.
                    </span>
                    {thread.anchor ? <span className="gone-quote">{thread.anchor.exact}</span> : null}
                </>
            ) : null}
            <span className="comments">
                {thread.comments.map((comment) => (
                    <CommentLine
                        key={comment.id}
                        comment={comment}
                        mine={account?.id === comment.author.id}
                        active={active}
                        onEdit={(body) => props.onEdit(comment.id, body)}
                        onDelete={() => props.onDelete(comment.id)}
                    />
                ))}
            </span>
            {thread.state === 'resolved' ? <span className="resolved-note">Resolved</span> : null}
            {active ? <Actions {...props} thread={thread} writable={writable} /> : null}
        </>
    )
}

function DraftBody({ thread, onReply, onClose }: ThreadNoteProps) {
    return (
        <>
            {thread.anchor ? null : <span className="gone-note text-muted">On the whole page</span>}
            <Composer
                placeholder={thread.anchor ? 'Comment on this passage' : 'Comment on the page'}
                submitLabel="Comment"
                focused
                onSubmit={onReply}
                onCancel={onClose}
            />
        </>
    )
}

function Actions(props: ThreadNoteProps & { thread: Thread }) {
    const { thread, account, writable, onReply, onResolve, onClose } = props
    if (!account) {
        return (
            <div className="actions">
                <SignInLink className="action action-primary">Sign in to reply</SignInLink>
            </div>
        )
    }
    if (thread.state === 'resolved') {
        return (
            <div className="actions">
                <button type="button" className="action" onClick={() => onResolve(false)}>
                    Reopen
                </button>
            </div>
        )
    }
    return (
        <>
            {writable ? (
                <Composer placeholder="Reply" submitLabel="Reply" onSubmit={onReply} onCancel={onClose} />
            ) : null}
            <div className="actions">
                <button type="button" className="action" onClick={() => onResolve(true)}>
                    Resolve
                </button>
            </div>
        </>
    )
}

function CommentLine(props: {
    comment: Comment
    mine: boolean
    active: boolean
    onEdit: (body: string) => Promise<unknown>
    onDelete: () => void
}) {
    const { comment, mine, active } = props
    const [editing, setEditing] = useState(false)
    const { author } = comment
    const deleted = comment.deleted_at !== null
    return (
        <span className={author.kind === 'agent' ? 'comment is-agent' : 'comment'}>
            <span className="who">{author.display_name}</span>
            {author.kind === 'agent' ? (
                <em className="agent-badge">
                    (Agent{author.on_behalf_of_name ? `, for ${author.on_behalf_of_name}` : ''})
                </em>
            ) : null}{' '}
            {editing ? (
                <Composer
                    placeholder="Edit"
                    submitLabel="Save"
                    initial={comment.body}
                    focused
                    onSubmit={(body) => props.onEdit(body).then(() => setEditing(false))}
                    onCancel={() => setEditing(false)}
                />
            ) : (
                <>
                    {deleted ? (
                        <span className="text-muted italic">Deleted.</span>
                    ) : (
                        <span className="body">{comment.body}</span>
                    )}
                    <span className="when">
                        {' '}
                        {ago(comment.created_at)}
                        {comment.edited_at && !deleted ? ', edited' : ''}
                    </span>
                    {mine && active && !deleted ? (
                        <span className="mine">
                            <button type="button" className="action" onClick={() => setEditing(true)}>
                                Edit
                            </button>
                            <button type="button" className="action" onClick={props.onDelete}>
                                Delete
                            </button>
                        </span>
                    ) : null}
                </>
            )}
        </span>
    )
}
