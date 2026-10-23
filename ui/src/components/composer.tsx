import { useState } from 'react'
import type { KeyboardEvent } from 'react'

/** What a composer does, and says. */
export interface ComposerProps {
    /** The field's placeholder, and its label. */
    placeholder: string
    /** The primary action's label: Comment, Reply, or Save. */
    submitLabel: string
    /** The text it starts with, when editing. */
    initial?: string
    /** Whether the field takes the focus when it appears: when the reader opened it themselves. */
    focused?: boolean
    /** Send the text: resolves once it is saved, and rejects with why it was not. */
    onSubmit: (body: string) => Promise<unknown>
    /** Leave without sending. */
    onCancel: () => void
}

/**
 * A single line that grows, with a faint underline that turns accent on focus; Ctrl or Cmd Enter sends, Escape
 * cancels (ui/DESIGN.md, "Threads").
 */
export function Composer({
    placeholder,
    submitLabel,
    initial = '',
    focused = false,
    onSubmit,
    onCancel,
}: ComposerProps) {
    const [body, setBody] = useState(initial)
    const [error, setError] = useState<string | null>(null)
    const [pending, setPending] = useState(false)

    const send = async () => {
        const text = body.trim()
        if (!text || pending) {
            return
        }
        setPending(true)
        setError(null)
        try {
            await onSubmit(text)
            setBody('')
        } catch (error_) {
            setError(error_ instanceof Error ? error_.message : 'It did not save. Try again.')
        } finally {
            setPending(false)
        }
    }

    const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
        if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
            event.preventDefault()
            void send()
        } else if (event.key === 'Escape') {
            event.preventDefault()
            event.stopPropagation()
            onCancel()
        }
    }

    return (
        <form
            className="composer"
            onSubmit={(event) => {
                event.preventDefault()
                void send()
            }}
        >
            <textarea
                rows={1}
                value={body}
                placeholder={placeholder}
                aria-label={placeholder}
                maxLength={4000}
                // oxlint-disable-next-line jsx-a11y/no-autofocus -- the reader asked for this field by opening it
                autoFocus={focused}
                onChange={(event) => {
                    setBody(event.target.value)
                    const field = event.target
                    field.style.height = 'auto'
                    field.style.height = `${field.scrollHeight}px`
                }}
                onKeyDown={onKeyDown}
            />
            {error ? (
                <p role="alert" className="mt-1 font-ui text-xs text-accent">
                    {error}
                </p>
            ) : null}
            <div className="actions">
                <button type="submit" className="action action-primary" disabled={pending || !body.trim()}>
                    {submitLabel}
                </button>
                <button type="button" className="action" onClick={onCancel}>
                    Cancel
                </button>
                <span className="kbd-hint">Ctrl Enter</span>
            </div>
        </form>
    )
}
