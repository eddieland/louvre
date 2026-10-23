import { createFileRoute } from '@tanstack/react-router'

/** The specimen: Annotated's tokens and type on one page, until M2's pages replace it (ui/DESIGN.md). */
export const Route = createFileRoute('/')({
    component: Specimen,
})

function Specimen() {
    return (
        <main className="stage">
            <article className="sheet">
                <p className="label">Specimen &middot; ui/DESIGN.md</p>
                <div className="reading">
                    <h1 className="title">A gallery at night</h1>
                    <p className="mt-5">
                        The artifact is the exhibit, hung on a warm wall in a frame of its own.{' '}
                        <mark className="anchor">The conversation is marginalia</mark>
                        <sup className="text-accent">1</sup>, set beside the passage it speaks to, numbered like a
                        sidenote. A number keeps its unit: 1.2&nbsp;s.
                    </p>
                    <h2 className="mt-8 heading">Tokens</h2>
                    <p className="mt-2 text-muted">
                        Muted text for what Louvre says about a page. The accent marks what is live: a{' '}
                        <a className="text-accent underline underline-offset-4" href="/directions">
                            link to the design study
                        </a>
                        .
                    </p>
                </div>
            </article>
            <aside className="note" aria-label="A margin note">
                <span className="note-n">1</span>
                <span className="note-who">Ana Ruiz</span> Should this read as a note or a card?
                <span className="mt-2 block">
                    <span className="note-who">canopy worker</span>{' '}
                    <em className="text-muted">(Agent, for Sam Okafor)</em> A note, per the direction picked.
                </span>
            </aside>
        </main>
    )
}
