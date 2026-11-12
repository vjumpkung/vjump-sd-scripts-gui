import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '')

    return {
        plugins: [react(), tailwindcss()],
        resolve: {
            alias: {
                '@': fileURLToPath(new URL('./src', import.meta.url))
            }
        },
        server: {
            proxy: {
                // Forward API calls to the FastAPI backend during development.
                '/api': {
                    target: env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000',
                    changeOrigin: true
                }
            }
        },
        build: {
            // The production build is hosted by the FastAPI backend from its web/ folder.
            outDir: '../backend/web',
            emptyOutDir: true
        }
    }
})
