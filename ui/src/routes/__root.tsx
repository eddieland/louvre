import type { QueryClient } from '@tanstack/react-query'
import { createRootRouteWithContext, Link, Outlet } from '@tanstack/react-router'

/** What every route's loader can reach. */
export interface RouterContext {
    /** The one Query client, so a loader can prime the cache a page reads. */
    queryClient: QueryClient
}

/** The shell around every page: Louvre's one-line header on the wall, then the page. */
export const Route = createRootRouteWithContext<RouterContext>()({
    component: RootLayout,
})

function RootLayout() {
    return (
        <div className="min-h-dvh bg-wall text-ink">
            <header className="flex items-baseline justify-between gap-3 px-5 pt-4 pb-2 sm:px-8 sm:pt-7">
                <Link to="/" className="wordmark text-ink">
                    Louvre
                </Link>
            </header>
            <Outlet />
        </div>
    )
}
