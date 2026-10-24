// What Louvre says about a decision in a line, and how its page names and orders decisions.

import type { Decision, DecisionOption } from '@/lib/api'
import { count } from '@/lib/format'

/** The id the page marks an option's passage under, so the bridge lights it while the option is hovered. */
export function passageId(decision: Decision, option: DecisionOption): string {
    return `option:${decision.id}:${option.id}`
}

/**
 * Say who has answered and who it still waits on, in one line, such as "1 answer. Waiting on you, Raj Patel.": the
 * reader, by their login `me`, first and as "you".
 */
export function waiting(decision: Decision, me?: string): string {
    const answered = count(decision.answers.length, 'answer')
    const mine = (login: string) => login === me?.toLowerCase()
    const waitingOn = decision.asked
        .filter((p) => !p.answered)
        .toSorted((a, b) => Number(mine(b.login)) - Number(mine(a.login)))
        .map((p) => (mine(p.login) ? 'you' : (p.name ?? p.login)))
    if (decision.state === 'closed' || waitingOn.length === 0) {
        return `${answered}.`
    }
    return `${answered}. Waiting on ${waitingOn.join(', ')}.`
}

/** Say in a line where a decision stands, for one shown closed up, to the reader whose login is `me`. */
export function summary(decision: Decision, me?: string): string {
    if (decision.state === 'closed') {
        return count(decision.answers.length, 'answer')
    }
    if (decision.mine) {
        const chose = decision.mine.choices.map((c) => labelOf(decision, c)).join(', ')
        return `You chose ${chose}. ${waiting(decision, me)}`
    }
    return `${count(decision.options.length, 'option')}. ${waiting(decision, me)}`
}

/** Name an option by its id, or give the id back for one the decision does not offer. */
export function labelOf(decision: Decision, id: string): string {
    return decision.options.find((o) => o.id === id)?.label ?? id
}

/** Where a decision sorts on an artifact's page: awaiting the reader first, then open, then closed. */
export function rank(decision: Decision): number {
    if (decision.awaits_me) {
        return 0
    }
    return decision.state === 'open' ? 1 : 2
}
