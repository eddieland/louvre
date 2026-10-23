import './index.css'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createRouter, RouterProvider } from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { routeTree } from './routeTree.gen'

const queryClient = new QueryClient()

const router = createRouter({
    routeTree,
    // Vite's `base`: FastAPI serves the SPA under /app/ (vite.config.ts).
    basepath: '/app',
    context: { queryClient },
    defaultPreload: 'intent',
    // Loaders read the Query cache; the router keeps no cache of its own.
    defaultPreloadStaleTime: 0,
    scrollRestoration: true,
})

declare module '@tanstack/react-router' {
    interface Register {
        router: typeof router
    }
}

const root = document.querySelector('#root')
if (!root) {
    throw new Error('index.html has no #root')
}

createRoot(root).render(
    <StrictMode>
        <QueryClientProvider client={queryClient}>
            <RouterProvider router={router} />
        </QueryClientProvider>
    </StrictMode>,
)
