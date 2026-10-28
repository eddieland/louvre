// The browser tab's title: the page's, then the deployment's name, which its owner may give (louvre.web.site).

import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'

import { sessionQuery } from '@/lib/api'

/** What a deployment is called when its owner gives it no name. */
export const DEFAULT_NAME = 'Louvre'

/** Make a tab's title: `page`, if any, then `name`, the deployment's, or Louvre's. */
export function titleOf(page: string | undefined, name: string): string {
    const site = name.trim() || DEFAULT_NAME
    return page ? `${page} · ${site}` : site
}

/** Title the tab for `page`, or for the deployment alone, while the calling page is shown. */
export function usePageTitle(page?: string): void {
    const name = useQuery(sessionQuery).data?.site.name ?? ''
    useEffect(() => {
        document.title = titleOf(page, name)
    }, [page, name])
}
