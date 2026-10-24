import type { MarkedChange } from '@/lib/changes'
import { kindOf } from '@/lib/changes'

/** A change as the margin notes it, and what the reader can do with it. */
export interface ChangeNoteProps {
    /** The change. */
    change: MarkedChange
    /** Whether it is the active note, its passage lit. */
    active: boolean
    /** Whether it or its passage is hovered. */
    hovered: boolean
    /** Make it the active note. */
    onActivate: () => void
    /** The pointer came onto it, or left it. */
    onHover: (on: boolean) => void
}

/**
 * One change in the margin, level with its passage: what kind it is, the words it removed struck through, and the
 * words it added, which the frame also marks (ui/DESIGN.md, "Changes").
 */
export function ChangeNote({ change, active, hovered, onActivate, onHover }: ChangeNoteProps) {
    const classes = ['thread', 'change', active ? 'is-active' : '', hovered ? 'is-hover' : ''].filter(Boolean).join(' ')
    return (
        // oxlint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- hover only lights the passage
        <section
            className={classes}
            data-id={change.id}
            data-kind={change.kind}
            aria-label={kindOf(change)}
            onMouseEnter={() => onHover(true)}
            onMouseLeave={() => onHover(false)}
        >
            <button type="button" className="thread-open" onClick={onActivate}>
                <span className="change-kind">{kindOf(change)}</span>
                {change.removed ? <span className="gone-quote clamp">{change.removed}</span> : null}
                {change.added ? <span className="change-added clamp">{change.added}</span> : null}
            </button>
        </section>
    )
}
