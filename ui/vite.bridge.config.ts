import { defineConfig } from 'vite'

/**
 * The bridge's build: src/bridge/main.ts as one self-contained script, dist/bridge/bridge.js, which the server adds to
 * every artifact's page (louvre.web.ui.bridge). It runs after the app's build, into the same dist, and keeps it.
 */
export default defineConfig({
    build: {
        outDir: 'dist/bridge',
        emptyOutDir: false,
        target: 'es2022',
        lib: {
            entry: 'src/bridge/main.ts',
            formats: ['iife'],
            name: 'louvreBridge',
            fileName: () => 'bridge.js',
        },
    },
})
