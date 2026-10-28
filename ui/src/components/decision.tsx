import { useState } from 'react'

import { SignInLink } from '@/components/sign-in'
import { ApiError, useDecisionWrites } from '@/lib/api'
import type { Account, Decision, DecisionOption } from '@/lib/api'
import { labelOf, summary, waiting } from '@/lib/decisions'
import { ago, count } from '@/lib/format'

/** A decision as an artifact's page shows it, and what the reader can do with it. */
export interface DecisionCardProps {
    /** The decision. */
    decision: Decision
    /** The signed-in person, who may answer, or null for a reader who may not. */
    account: Account | null
    /** Whether it shows whole: its options, and its answers; otherwise one line that opens it. */
    open: boolean
    /** Show it whole, or as one line. */
    onToggle: () => void
    /** An option's passage is to be lit in the page, or none. */
    onLight: (option: DecisionOption | null) => void
    /** Scroll the page to an option's passage. */
    onShow: (option: DecisionOption) => void
}

/**
 * A question asked on the artifact, answered by choosing (ui/DESIGN.md, "Decisions"): its options, which light their
 * passages in the page, and once the reader has answered, or it is closed, how many chose each, and who.
 */
export function DecisionCard(props: DecisionCardProps) {
    const { decision, open } = props
    const closed = decision.state === 'closed'
    const outcome = decision.options.find((o) => o.id === decision.outcome)
    return (
        <section
            id={`decision-${decision.id}`}
            className="decision"
            data-state={decision.state}
            data-awaiting={decision.awaits_me ? '' : undefined}
            aria-label={`Decision: ${decision.question}`}
        >
            <p className="decision-label">
                <span className={decision.awaits_me ? 'text-accent' : undefined}>
                    {closed ? 'Decided' : decision.awaits_me ? 'Your answer is wanted' : 'Decision'}
                </span>
                <span>
                    asked by {decision.author.display_name}
                    {decision.author.kind === 'agent' ? (
                        <em>
                            {' '}
                            (Agent
                            {decision.author.on_behalf_of_name ? `, for ${decision.author.on_behalf_of_name}` : ''})
                        </em>
                    ) : null}
                </span>
                <span>{ago(closed && decision.closed_at ? decision.closed_at : decision.created_at)}</span>
            </p>
            <h2 className="decision-question">
                <button type="button" className="decision-toggle" aria-expanded={open} onClick={props.onToggle}>
                    {decision.question}
                </button>
            </h2>
            {open ? (
                <Whole {...props} />
            ) : (
                <p className="decision-summary">
                    {outcome ? (
                        <>
                            <b>{outcome.label}</b>
                            {' · '}
                        </>
                    ) : null}
                    {summary(decision, props.account?.login)}
                </p>
            )}
        </section>
    )
}

function Whole(props: DecisionCardProps) {
    const { decision, account } = props
    const closed = decision.state === 'closed'
    const [changing, setChanging] = useState(false)
    // A reader sees how others chose once they have answered, or it is closed, or they cannot answer: never before
    // they choose, so the count does not sway them.
    const answering = !closed && account !== null && (decision.mine === null || changing)
    return (
        <>
            {answering ? (
                <AnswerForm {...props} onDone={() => setChanging(false)} onCancel={() => setChanging(false)} />
            ) : (
                <Results {...props} />
            )}
            {closed && decision.outcome_note ? <p className="decision-note">{decision.outcome_note}</p> : null}
            <p className="decision-meta">
                {waiting(decision, account?.login)}
                {!closed && account === null ? (
                    <>
                        {' '}
                        <SignInLink className="link">Sign in to answer</SignInLink>
                    </>
                ) : null}
            </p>
            {answering ? null : (
                <div className="actions">
                    {!closed && decision.mine ? (
                        <button type="button" className="action action-primary" onClick={() => setChanging(true)}>
                            Change your answer
                        </button>
                    ) : null}
                    {decision.may_close ? <CloseForm decision={decision} /> : null}
                </div>
            )}
        </>
    )
}

function AnswerForm(props: DecisionCardProps & { onDone: () => void; onCancel: () => void }) {
    const { decision, onLight, onShow } = props
    const { answer } = useDecisionWrites()
    const [choices, setChoices] = useState<string[]>(decision.mine?.choices ?? [])
    const [note, setNote] = useState(decision.mine?.note ?? '')
    const [error, setError] = useState<string | null>(null)
    const kind = decision.multiple ? 'checkbox' : 'radio'

    const pick = (id: string, on: boolean) => {
        if (!decision.multiple) {
            setChoices([id])
            return
        }
        setChoices((had) => (on ? [...had.filter((c) => c !== id), id] : had.filter((c) => c !== id)))
    }

    const send = async () => {
        setError(null)
        try {
            await answer.mutateAsync({ decisionId: decision.id, choices, note: note.trim() })
            props.onDone()
        } catch (error_) {
            setError(error_ instanceof ApiError ? error_.message : 'It did not save. Try again.')
        }
    }

    return (
        <form
            className="decision-form"
            onSubmit={(event) => {
                event.preventDefault()
                void send()
            }}
        >
            <fieldset className="options">
                <legend className="sr-only">{decision.multiple ? 'Choose any' : 'Choose one'}</legend>
                {decision.options.map((option) => (
                    <div
                        key={option.id}
                        className="option"
                        onMouseEnter={() => onLight(option)}
                        onMouseLeave={() => onLight(null)}
                    >
                        <label className="option-choice">
                            <input
                                type={kind}
                                name={`decision-${decision.id}`}
                                value={option.id}
                                checked={choices.includes(option.id)}
                                onChange={(event) => pick(option.id, event.target.checked)}
                                onFocus={() => onLight(option)}
                                onBlur={() => onLight(null)}
                            />
                            <span>
                                <span className="option-label">{option.label}</span>
                                {option.detail ? <span className="option-detail">{option.detail}</span> : null}
                            </span>
                        </label>
                        {option.anchor ? <PassageLink option={option} onShow={onShow} /> : null}
                    </div>
                ))}
            </fieldset>
            <textarea
                className="decision-field"
                rows={1}
                value={note}
                placeholder="Add a note (optional)"
                aria-label="Add a note (optional)"
                maxLength={4000}
                onChange={(event) => {
                    setNote(event.target.value)
                    const field = event.target
                    field.style.height = 'auto'
                    field.style.height = `${field.scrollHeight}px`
                }}
            />
            {error ? (
                <p role="alert" className="mt-1 font-ui text-xs text-accent">
                    {error}
                </p>
            ) : null}
            <div className="actions">
                <button type="submit" className="button" disabled={choices.length === 0 || answer.isPending}>
                    {decision.mine ? 'Save your answer' : 'Answer'}
                </button>
                {decision.mine ? (
                    <button type="button" className="action" onClick={props.onCancel}>
                        Cancel
                    </button>
                ) : null}
            </div>
        </form>
    )
}

function Results({ decision, onLight, onShow }: DecisionCardProps) {
    const most = Math.max(1, ...decision.options.map((o) => o.count))
    const total = decision.answers.length
    return (
        <>
            <ol className="options">
                {decision.options.map((option) => (
                    <Result
                        key={option.id}
                        option={option}
                        most={most}
                        mine={decision.mine?.choices.includes(option.id) === true}
                        chosen={decision.outcome === option.id}
                        onLight={onLight}
                        onShow={onShow}
                    />
                ))}
            </ol>
            {total > 0 ? (
                <ul className="answers" aria-label="Answers">
                    {decision.answers.map((a) => (
                        <li key={a.account_id}>
                            <span className="who">{a.name}</span>{' '}
                            <span className="text-muted">
                                chose {a.choices.map((c) => labelOf(decision, c)).join(', ')}
                            </span>
                            {a.note ? <span className="answer-note">{a.note}</span> : null}
                            <span className="when"> {ago(a.answered_at)}</span>
                        </li>
                    ))}
                </ul>
            ) : null}
        </>
    )
}

/** One option among the results: its label, how many chose it as a number and a bar, and its passage. */
function Result(props: {
    option: DecisionOption
    most: number
    mine: boolean
    chosen: boolean
    onLight: (option: DecisionOption | null) => void
    onShow: (option: DecisionOption) => void
}) {
    const { option, mine, chosen } = props
    return (
        // oxlint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- hover lights a passage
        <li
            className="option"
            data-mine={mine ? '' : undefined}
            data-outcome={chosen ? '' : undefined}
            onMouseEnter={() => props.onLight(option)}
            onMouseLeave={() => props.onLight(null)}
        >
            <span className="option-result">
                <span>
                    <span className="option-label">{option.label}</span>
                    {chosen ? <span className="option-tag">decided</span> : null}
                    {mine ? <span className="option-tag">your choice</span> : null}
                    {option.detail ? <span className="option-detail">{option.detail}</span> : null}
                </span>
                <span className="option-count" aria-label={count(option.count, 'answer')}>
                    {option.count}
                </span>
            </span>
            <span className="tally" aria-hidden="true">
                <span style={{ width: `${String((option.count / props.most) * 100)}%` }} />
            </span>
            {option.anchor ? <PassageLink option={option} onShow={props.onShow} /> : null}
        </li>
    )
}

/** The link to an option's passage, or its place on the artifact's map, which the map pans and zooms to. */
function PassageLink({ option, onShow }: { option: DecisionOption; onShow: (option: DecisionOption) => void }) {
    const what = option.place ? 'place' : 'passage'
    return (
        <button
            type="button"
            className="action option-passage"
            onClick={() => onShow(option)}
            aria-label={`Show the ${what} for ${option.label}`}
        >
            {option.place ? 'Place' : 'Passage'} &darr;
        </button>
    )
}

function CloseForm({ decision }: { decision: Decision }) {
    const { close } = useDecisionWrites()
    const [closing, setClosing] = useState(false)
    const [outcome, setOutcome] = useState('')
    const [note, setNote] = useState('')
    if (!closing) {
        return (
            <button type="button" className="action" onClick={() => setClosing(true)}>
                Close
            </button>
        )
    }
    return (
        <form
            className="decision-close"
            onSubmit={(event) => {
                event.preventDefault()
                close.mutate({ decisionId: decision.id, outcome: outcome || null, note: note.trim() })
            }}
        >
            <label className="label" htmlFor={`outcome-${decision.id}`}>
                Decided on
            </label>
            <select
                id={`outcome-${decision.id}`}
                className="field"
                value={outcome}
                onChange={(event) => setOutcome(event.target.value)}
            >
                <option value="">No one option</option>
                {decision.options.map((o) => (
                    <option key={o.id} value={o.id}>
                        {o.label}
                    </option>
                ))}
            </select>
            <input
                className="field"
                value={note}
                placeholder="Why (optional)"
                aria-label="Why (optional)"
                maxLength={4000}
                onChange={(event) => setNote(event.target.value)}
            />
            <div className="actions">
                <button type="submit" className="action action-primary" disabled={close.isPending}>
                    Close the decision
                </button>
                <button type="button" className="action" onClick={() => setClosing(false)}>
                    Cancel
                </button>
            </div>
        </form>
    )
}
