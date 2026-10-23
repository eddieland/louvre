import type { QueryClient } from '@tanstack/react-query'
import { createRootRouteWithContext, Outlet } from '@tanstack/react-router'

/** What every route's loader can reach. */
export interface RouterContext {
    /** The one Query client, so a loader can prime the cache a page reads. */
    queryClient: QueryClient
}

/** The wall every page hangs on; each page sets its own header, which names what it is. */
export const Route = createRootRouteWithContext<RouterContext>()({
    component: RootLayout,
})

function RootLayout() {
    return (
        <div className="min-h-dvh bg-wall text-ink">
            <Outlet />
        </div>
    )
}
