import { fileURLToPath } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import type { Plugin } from 'vite'

// The FastAPI server the dev server proxies to: `npm run dev:api` starts it.
const api = process.env.LOUVRE_API ?? 'http://127.0.0.1:8765'

// Fonts to preload: the latin subset of each self-hosted family. Others load on demand by unicode-range.
const PRELOAD_FONTS = /^(fraunces|source-serif-4|instrument-sans)-latin-wght-normal-.*\.woff2$/u

/** Adds a <link rel="preload"> for each font PRELOAD_FONTS matches, so text never paints in a fallback face. */
function preloadFonts(): Plugin {
    return {
        name: 'louvre:preload-fonts',
        apply: 'build',
        transformIndexHtml(_html, ctx) {
            const fonts = Object.keys(ctx.bundle ?? {}).filter((file) =>
                PRELOAD_FONTS.test(file.split('/').pop() ?? ''),
            )
            return fonts.map((file) => ({
                tag: 'link',
                attrs: { rel: 'preload', as: 'font', type: 'font/woff2', href: `/${file}`, crossorigin: '' },
                injectTo: 'head',
            }))
        },
    }
}

/** The SPA's build and dev server: file-based routes, the React Compiler, Tailwind, and `/api` proxied in dev. */
export default defineConfig({
    // Served by FastAPI at the root (louvre.web.app), every path it does not route being the SPA's.
    base: '/',
    plugins: [
        // Before react(): it generates src/routeTree.gen.ts from src/routes/.
        tanstackRouter({ target: 'react', autoCodeSplitting: true }),
        react({ compiler: true }),
        tailwindcss(),
        preloadFonts(),
    ],
    resolve: {
        alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    server: {
        host: '127.0.0.1',
        port: 5173,
        strictPort: true,
        proxy: Object.fromEntries(['/api', '/auth', '/content', '/mcp'].map((p) => [p, { target: api }])),
    },
    build: {
        outDir: 'dist',
        emptyOutDir: true,
        assetsDir: 'assets',
        // Fonts stay files, never inlined data: URLs, so they cache and preload.
        assetsInlineLimit: 0,
    },
})
