// The bridge: the one script Louvre adds to an artifact's page, at its end, inside the sandboxed frame.
//
// It reads the page's text as the server does (./text), finds each thread's passage in it, and marks it with the CSS
// Custom Highlight API, which paints over the page's own text and changes none of its markup. It tells the page that
// frames it where each passage is and how tall the page is, so the frame grows to the page and the margin sets each
// thread level with its passage, and it quotes what the reader selects as an anchor. The page it was added to keeps
// working as its author wrote it; the bridge's only elements, a stylesheet and the threads' numbers, are marked
// data-louvre, and the text skips them.

import { CHANNEL, KEYS } from './protocol'
import type { Colors, FromBridge, Mark, Place, Selected, ToBridge } from './protocol'
import { locate, quote, readText } from './text'
import type { PageText } from './text'

/** The most characters of a passage, as the server's MAX_EXACT. */
const MAX_EXACT = 4000
/** How many layouts in a row may grow the page with the frame before the page is taken to fill whatever it is given. */
const RUNAWAY = 3

function own(element: Element): boolean {
    return element instanceof HTMLElement && 'louvre' in element.dataset
}

function start(): void {
    const host = globalThis.parent
    if (host === globalThis.window) {
        // Opened alone, not in Louvre's frame: there is nothing to tell.
        return
    }
    const send = (message: FromBridge) => host.postMessage(message, '*')
    const doc = document
    const sheet = doc.createElement('style')
    sheet.dataset['louvre'] = ''
    const numbers = doc.createElement('div')
    numbers.dataset['louvre'] = ''
    numbers.setAttribute('aria-hidden', 'true')
    numbers.style.cssText = 'position:absolute;top:0;left:0;width:0;height:0;pointer-events:none;z-index:2147483647'
    ;((doc.body as HTMLElement | null) ?? doc.documentElement).append(sheet, numbers)

    let read: PageText = readText(doc.documentElement, own)
    let marks: Mark[] = []
    let active: string | null = null
    let hover: string | null = null
    let colors: Colors | null = null
    let ranges = new Map<string, Range>()
    let lastHeight = 0
    let lastViewport = 0
    let growing = 0
    let pending = 0
    let reread = false

    const locateAll = () => {
        ranges = new Map()
        for (const mark of marks) {
            const at = locate(read.text, mark.anchor)
            const range = at === null ? null : read.range(at, at + mark.anchor.exact.length)
            if (range) {
                ranges.set(mark.id, range)
            }
        }
    }

    const paint = () => {
        if (colors) {
            sheet.textContent =
                `::highlight(louvre-rest){background-color:${colors.rest}}` +
                `::highlight(louvre-strong){background-color:${colors.strong}}` +
                `::highlight(louvre-resolved){background-color:${colors.resolved}}` +
                'html[data-louvre-pointer],html[data-louvre-pointer] *{cursor:pointer!important}'
        }
        const rest: Range[] = []
        const strong: Range[] = []
        const resolved: Range[] = []
        const shown: [Mark, Range][] = []
        for (const mark of marks) {
            const range = ranges.get(mark.id)
            if (!range) {
                continue
            }
            const lit = mark.id === active || mark.id === hover
            if (mark.state === 'resolved') {
                if (lit) {
                    resolved.push(range)
                }
            } else {
                ;(lit ? strong : rest).push(range)
            }
            shown.push([mark, range])
        }
        if ('highlights' in CSS) {
            CSS.highlights.set('louvre-rest', new Highlight(...rest))
            const lit = new Highlight(...strong)
            lit.priority = 1
            CSS.highlights.set('louvre-strong', lit)
            CSS.highlights.set('louvre-resolved', new Highlight(...resolved))
        }
        const placed: HTMLElement[] = []
        for (const [mark, range] of shown) {
            const last = [...range.getClientRects()].at(-1)
            if (mark.n === null || !last) {
                continue
            }
            const n = doc.createElement('span')
            n.textContent = String(mark.n)
            n.style.cssText =
                `position:absolute;left:${last.right + scrollX + 1}px;top:${last.top + scrollY - 6}px;` +
                `font:600 11px/1 system-ui,sans-serif;color:${colors?.accent ?? 'inherit'}`
            placed.push(n)
        }
        numbers.replaceChildren(...placed)
    }

    const measure = (): number => {
        const body = doc.body as HTMLElement | null
        if (!body) {
            return doc.documentElement.scrollHeight
        }
        const style = getComputedStyle(body)
        const box = body.getBoundingClientRect()
        const bottom = box.bottom + scrollY + Number.parseFloat(style.marginBottom)
        return Math.ceil(Math.max(bottom, body.scrollHeight))
    }

    const report = () => {
        let height = measure()
        // A page sized to the viewport (min-height: 100vh and a margin, say) grows each time the frame does. When it
        // has grown with the frame RUNAWAY times in a row, it keeps the height it has.
        const viewport = innerHeight
        if (height > lastHeight && viewport > lastViewport && height - viewport === lastHeight - lastViewport) {
            growing++
        } else if (height !== lastHeight) {
            growing = 0
        }
        if (growing >= RUNAWAY) {
            height = lastHeight
        }
        lastHeight = height
        lastViewport = viewport
        const places: Record<string, Place> = {}
        for (const [id, range] of ranges) {
            const rects = [...range.getClientRects()]
            const first = rects[0]
            const last = rects.at(-1)
            if (first && last) {
                places[id] = { top: first.top + scrollY, bottom: last.bottom + scrollY }
            }
        }
        send({ channel: CHANNEL, type: 'layout', height, places })
    }

    const refresh = (again: boolean) => {
        reread ||= again
        if (pending !== 0) {
            return
        }
        pending = requestAnimationFrame(() => {
            pending = 0
            if (reread) {
                reread = false
                read = readText(doc.documentElement, own)
                locateAll()
            }
            paint()
            report()
        })
    }

    const hit = (x: number, y: number): string | null => {
        for (const mark of marks) {
            const range = ranges.get(mark.id)
            if (!range) {
                continue
            }
            for (const rect of range.getClientRects()) {
                if (x >= rect.left - 1 && x <= rect.right + 1 && y >= rect.top - 1 && y <= rect.bottom + 1) {
                    return mark.id
                }
            }
        }
        return null
    }

    globalThis.addEventListener('message', (event: MessageEvent<unknown>) => {
        const data = event.data
        if (event.source !== host || typeof data !== 'object' || data === null || !('channel' in data)) {
            return
        }
        if (data.channel !== CHANNEL) {
            return
        }
        const message = data as ToBridge
        if (message.type === 'clear-selection') {
            getSelection()?.removeAllRanges()
            return
        }
        marks = message.marks
        active = message.active
        hover = message.hover
        colors = message.colors
        locateAll()
        paint()
        report()
    })

    doc.addEventListener('selectionchange', () => {
        requestAnimationFrame(() => {
            send({ channel: CHANNEL, type: 'selection', selected: selected() })
        })
    })

    const selected = (): Selected | null => {
        const selection = getSelection()
        if (!selection || selection.isCollapsed || selection.rangeCount === 0) {
            return null
        }
        const range = selection.getRangeAt(0)
        const span = read.span(range)
        if (!span) {
            return null
        }
        const box = range.getBoundingClientRect()
        const anchor = span.end - span.start > MAX_EXACT ? null : quote(read.text, span.start, span.end)
        return { anchor, top: box.top + scrollY, bottom: box.bottom + scrollY, left: box.left, right: box.right }
    }

    doc.addEventListener('click', (event) => {
        if (getSelection()?.isCollapsed === false) {
            return
        }
        const id = hit(event.clientX, event.clientY)
        const link = event.target instanceof Element ? event.target.closest('a[href]') : null
        if (id === null && link instanceof HTMLAnchorElement && !link.getAttribute('href')?.startsWith('#')) {
            // A link leaves the frame for a tab of its own, never replacing the artifact in Louvre's page.
            link.target = '_blank'
            link.rel = 'noopener noreferrer'
        }
        send({ channel: CHANNEL, type: 'click', id })
    })

    let hoverFrame = 0
    doc.addEventListener('pointermove', (event) => {
        if (hoverFrame !== 0 || event.pointerType !== 'mouse') {
            return
        }
        hoverFrame = requestAnimationFrame(() => {
            hoverFrame = 0
            const id = hit(event.clientX, event.clientY)
            if (id !== hover) {
                hover = id
                if (id === null) {
                    delete doc.documentElement.dataset['louvrePointer']
                } else {
                    doc.documentElement.dataset['louvrePointer'] = ''
                }
                send({ channel: CHANNEL, type: 'hover', id })
            }
        })
    })
    doc.addEventListener('pointerleave', () => {
        delete doc.documentElement.dataset['louvrePointer']
        send({ channel: CHANNEL, type: 'hover', id: null })
    })

    doc.addEventListener('keydown', (event) => {
        const target = event.target instanceof Element ? event.target : null
        if (
            event.metaKey ||
            event.ctrlKey ||
            event.altKey ||
            target?.closest('input, textarea, select, [contenteditable]')
        ) {
            return
        }
        const key = KEYS.find((k) => k === event.key)
        if (key) {
            if (key === 'c') {
                event.preventDefault()
            }
            send({ channel: CHANNEL, type: 'key', key })
        }
    })

    new ResizeObserver(() => refresh(false)).observe(doc.documentElement)
    const body = doc.body as HTMLElement | null
    if (body) {
        new ResizeObserver(() => refresh(false)).observe(body)
    }
    new MutationObserver((records) => {
        if (records.some((r) => !(r.target instanceof Element && own(r.target)) && !numbers.contains(r.target))) {
            refresh(true)
        }
    }).observe(doc.documentElement, { childList: true, characterData: true, subtree: true })
    globalThis.addEventListener('load', () => refresh(true))
    void doc.fonts.ready.then(() => refresh(false))
    send({ channel: CHANNEL, type: 'ready' })
    report()
}

start()
