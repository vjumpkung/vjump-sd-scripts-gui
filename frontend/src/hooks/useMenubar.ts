import { create } from 'zustand'

export type Page = 'training' | 'datasets' | 'downloads' | 'jobs' | 'settings' | 'about'

type MenuState = {
    page: Page
    // The model family shown on the training page. null until the preset list has loaded.
    family: string | null
    go: (page: Page, family?: string) => void
}

const useMenuBar = create<MenuState>((set) => ({
    page: 'training',
    family: null,
    go: (page, family) =>
        set((state) => ({
            page,
            family: family ?? state.family
        }))
}))

export default useMenuBar
