import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ThemeMode = 'system' | 'light' | 'dark'

type ThemeState = {
    mode: ThemeMode
    // The resolved theme. Derived from `mode` and the system preference, never persisted.
    dark: boolean
    setMode: (mode: ThemeMode) => void
    toggle: () => void
}

const systemQuery = () =>
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
        ? window.matchMedia('(prefers-color-scheme: dark)')
        : null

const resolveDark = (mode: ThemeMode) =>
    mode === 'dark' || (mode === 'system' && Boolean(systemQuery()?.matches))

// Transitions are disabled for the swap so the whole page changes at once (DESIGN.md, Motion).
const applyTheme = (dark: boolean) => {
    const root = document.documentElement
    if (root.classList.contains('dark') === dark) return

    root.classList.add('no-transitions')
    root.classList.toggle('dark', dark)
    // Force a style recalculation before the transitions come back.
    void root.offsetHeight
    window.requestAnimationFrame(() =>
        window.requestAnimationFrame(() => root.classList.remove('no-transitions'))
    )
}

const useTheme = create<ThemeState>()(
    persist(
        (set, get) => ({
            mode: 'system',
            dark:
                typeof document !== 'undefined' &&
                document.documentElement.classList.contains('dark'),
            setMode: (mode) => set({ mode, dark: resolveDark(mode) }),
            toggle: () => {
                const next: ThemeMode = get().dark ? 'light' : 'dark'
                set({ mode: next, dark: next === 'dark' })
            }
        }),
        {
            name: 'sdgui:theme',
            version: 1,
            partialize: (state) => ({ mode: state.mode }),
            onRehydrateStorage: () => (state) => {
                if (state) state.setMode(state.mode)
            }
        }
    )
)

/** Keeps the <html> class in sync with the store. Call once, before the first render. */
export const initTheme = () => {
    const sync = () => {
        const { mode } = useTheme.getState()
        const dark = resolveDark(mode)
        if (useTheme.getState().dark !== dark) useTheme.setState({ dark })
        applyTheme(dark)
    }

    sync()
    useTheme.subscribe((state, previous) => {
        if (state.mode !== previous.mode || state.dark !== previous.dark) applyTheme(state.dark)
    })
    systemQuery()?.addEventListener('change', () => {
        if (useTheme.getState().mode === 'system') sync()
    })
}

export default useTheme
