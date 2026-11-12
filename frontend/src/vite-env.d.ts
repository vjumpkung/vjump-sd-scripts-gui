/// <reference types="vite/client" />

interface Window {
    pywebview?: {
        api: {
            pick_path: (kind: 'file' | 'folder', start?: string | null) => Promise<string | null>
        }
    }
}
