import type { MarkedChange, MarkedFeature } from '@/lib/changes'
import { kindOf, movedBy } from '@/lib/changes'

/** A change as the margin notes it, and what the reader can do with it. */
export interface ChangeNoteProps {
    /** The change: to the version's words, or to a feature on its map. */
    change: MarkedChange | MarkedFeature
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
 * words it added, which the frame also marks (ui/DESIGN.md, "Changes"). A feature on a map is noted by its label, a
 * removed one's struck through, and for one moved, how far and which way, as the map lights it.
 */
export function ChangeNote({ change, active, hovered, onActivate, onHover }: ChangeNoteProps) {
    const classes = ['thread', 'change', active ? 'is-active' : '', hovered ? 'is-hover' : ''].filter(Boolean).join(' ')
    const onMap = 'feature' in change
    const kind = onMap ? kindOf(change.feature) : kindOf(change)
    return (
        // oxlint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- hover only lights the passage
        <section
            className={classes}
            data-id={change.id}
            data-kind={onMap ? change.feature.kind : change.kind}
            aria-label={onMap ? `${kind}: ${change.feature.label}` : kind}
            onMouseEnter={() => onHover(true)}
            onMouseLeave={() => onHover(false)}
        >
            <button type="button" className="thread-open" onClick={onActivate}>
                <span className="change-kind">{onMap ? `${kind} on the map` : kind}</span>
                {onMap ? <FeatureLines feature={change.feature} /> : <WordLines change={change} />}
            </button>
        </section>
    )
}

function WordLines({ change }: { change: MarkedChange }) {
    return (
        <>
            {change.removed ? <span className="gone-quote clamp">{change.removed}</span> : null}
            {change.added ? <span className="change-added clamp">{change.added}</span> : null}
        </>
    )
}

function FeatureLines({ feature }: { feature: MarkedFeature['feature'] }) {
    const moved = movedBy(feature)
    return (
        <>
            <span className={feature.kind === 'removed' ? 'gone-quote clamp' : 'change-added clamp'}>
                {feature.label}
            </span>
            {moved ? <span className="change-moved">{moved}</span> : null}
        </>
    )
}
