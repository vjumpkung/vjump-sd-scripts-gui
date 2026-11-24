import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { isIP } from 'node:net'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'

// Hosts Vite's own host check allows by default. A DNS-rebinding page can use none of them.
const isLocalHost = (host: string) => {
    const name = host
        .toLowerCase()
        .replace(/:\d+$/, '')
        .replace(/^\[(.*)\]$/, '$1')
    return name === 'localhost' || name.endsWith('.localhost') || isIP(name) !== 0
}

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
                    changeOrigin: true,
                    // The Socket.IO channel (/api/socket.io) upgrades to a WebSocket.
                    ws: true,
                    // changeOrigin gives the backend its own Host, and Chromium sends no
                    // Sec-Fetch-Site on a WebSocket handshake, so the backend matches the Origin
                    // against X-Forwarded-Host. `xfwd` does not set it on upgrades, and Vite's
                    // host check does not cover them, so only local hosts are vouched for.
                    configure: (proxy) => {
                        proxy.on('proxyReqWs', (proxyReq, req) => {
                            const host = req.headers.host
                            if (!host || !isLocalHost(host)) return
                            if (!proxyReq.hasHeader('x-forwarded-host')) {
                                proxyReq.setHeader('x-forwarded-host', host)
                            }
                        })
                    }
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
