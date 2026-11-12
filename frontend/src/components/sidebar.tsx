import { LanguageToggle, ThemeToggle } from './toggles'
import {
    AlertDialog,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
    SheetTrigger
} from '@/components/ui/sheet'
import useManagedUploadGuard from '@/hooks/useManagedUploadGuard'
import useMenuBar, { type Page } from '@/hooks/useMenubar'
import { usePresets, useSystemStatus } from '@/hooks/useSystem'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'
import {
    CloudDownloadIcon,
    DatabaseIcon,
    InfoIcon,
    MenuIcon,
    SettingsIcon,
    SquareTerminalIcon
} from 'lucide-react'
import { type ReactNode, useEffect, useRef, useState } from 'react'

type NavItemProps = {
    active: boolean
    icon?: ReactNode
    label: string
    indent?: boolean
    onClick: () => void
}

const NavItem = ({ active, icon, label, indent, onClick }: NavItemProps) => (
    <button
        type="button"
        aria-current={active ? 'page' : undefined}
        className={cn(
            'flex h-10 w-full items-center gap-3 rounded-full px-4 text-left text-[0.9375rem] transition-colors motion-reduce:transition-none',
            indent && 'pl-5',
            active
                ? 'bg-primary font-semibold text-ink'
                : 'font-medium text-muted-foreground hover:bg-muted hover:text-foreground'
        )}
        onClick={onClick}
    >
        {icon ? <span className="shrink-0 [&_svg]:size-[18px]">{icon}</span> : null}
        <span className="min-w-0 truncate">{label}</span>
    </button>
)

const Brand = () => {
    const { t } = useI18n()

    return (
        <div className="flex items-center gap-3">
            <img src="/logo.png" alt="" className="size-10 shrink-0 rounded-lg object-contain" />
            <div className="min-w-0">
                <p className="truncate text-base leading-tight font-bold tracking-[-0.01em]">
                    {t('app.name')}
                </p>
                <p className="text-xs text-muted-foreground">{t('app.by')}</p>
            </div>
        </div>
    )
}

const ExternalLinks = () => {
    const { t } = useI18n()
    const linkClass =
        'rounded-sm text-xs text-muted-foreground underline decoration-pink-ink decoration-[0.08em] underline-offset-[0.22em] hover:text-foreground'

    return (
        <div className="flex items-center gap-4">
            <a href="https://vjump.dev" target="_blank" rel="noreferrer" className={linkClass}>
                {t('nav.link.website')}
            </a>
            <a
                href="https://www.facebook.com/pixellatent"
                target="_blank"
                rel="noreferrer"
                className={linkClass}
            >
                {t('nav.link.facebook')}
            </a>
        </div>
    )
}

type NavigationBodyProps = {
    onSelect: (page: Page, family?: string) => void
}

const NavigationBody = ({ onSelect }: NavigationBodyProps) => {
    const { t, lookup } = useI18n()
    const page = useMenuBar((state) => state.page)
    const family = useMenuBar((state) => state.family)
    const presets = usePresets()
    const families = presets.data?.families ?? []
    // The default page is the first family, even before the user has picked one.
    const activeFamily = family && families.includes(family) ? family : families[0]

    return (
        <nav aria-label={t('nav.main')} className="flex flex-col gap-6">
            <div className="flex flex-col gap-1">
                <p className="px-4 pb-1 text-xs font-semibold tracking-[0.05em] text-muted-foreground uppercase">
                    {t('nav.training')}
                </p>
                {families.map((id) => (
                    <NavItem
                        key={id}
                        indent
                        active={page === 'training' && activeFamily === id}
                        label={lookup(`family.${id}`) ?? id}
                        onClick={() => onSelect('training', id)}
                    />
                ))}
                {presets.isPending ? (
                    <div className="flex flex-col gap-2 px-4 py-2" aria-hidden>
                        {[0, 1, 2, 3].map((index) => (
                            <div
                                key={index}
                                className="h-5 rounded-full bg-muted motion-safe:animate-pulse"
                            />
                        ))}
                    </div>
                ) : null}
            </div>

            <div className="flex flex-col gap-1">
                <NavItem
                    active={page === 'datasets'}
                    icon={<DatabaseIcon />}
                    label={t('nav.datasets')}
                    onClick={() => onSelect('datasets')}
                />
                <NavItem
                    active={page === 'downloads'}
                    icon={<CloudDownloadIcon />}
                    label={t('nav.downloads')}
                    onClick={() => onSelect('downloads')}
                />
                <NavItem
                    active={page === 'jobs'}
                    icon={<SquareTerminalIcon />}
                    label={t('nav.jobs')}
                    onClick={() => onSelect('jobs')}
                />
                <NavItem
                    active={page === 'settings'}
                    icon={<SettingsIcon />}
                    label={t('nav.settings')}
                    onClick={() => onSelect('settings')}
                />
                <NavItem
                    active={page === 'about'}
                    icon={<InfoIcon />}
                    label={t('nav.about')}
                    onClick={() => onSelect('about')}
                />
            </div>
        </nav>
    )
}

const SidebarFooter = () => {
    const status = useSystemStatus()

    return (
        <div className="flex flex-col gap-4 border-t border-border pt-4">
            <div className="flex items-center justify-between gap-3">
                <LanguageToggle />
                <ThemeToggle />
            </div>
            <div className="flex items-center justify-between gap-3">
                <ExternalLinks />
                {status.data ? (
                    <span className="tabular text-xs text-muted-foreground" translate="no">
                        v{status.data.version}
                    </span>
                ) : null}
            </div>
        </div>
    )
}

type SideBarProps = {
    onNavigationStart: () => void
    onNavigationComplete: () => void
}

const SideBar = ({ onNavigationStart, onNavigationComplete }: SideBarProps) => {
    const { t } = useI18n()
    const [mobileOpen, setMobileOpen] = useState(false)
    const [uploadBlockedOpen, setUploadBlockedOpen] = useState(false)
    const navigationPendingRef = useRef(false)
    const blockedFocusRef = useRef<HTMLElement | null>(null)

    const page = useMenuBar((state) => state.page)
    const family = useMenuBar((state) => state.family)
    const go = useMenuBar((state) => state.go)
    const uploading = useManagedUploadGuard()

    useEffect(() => {
        const desktop = window.matchMedia('(min-width: 64rem)')
        const closeOnDesktop = () => {
            if (desktop.matches) setMobileOpen(false)
        }
        desktop.addEventListener('change', closeOnDesktop)
        return () => desktop.removeEventListener('change', closeOnDesktop)
    }, [])

    const select = (target: Page, targetFamily?: string) => {
        const changing = target !== page || (target === 'training' && targetFamily !== family)

        // Leaving mid-upload would lose track of its progress and result.
        if (uploading && changing) {
            blockedFocusRef.current =
                document.activeElement instanceof HTMLElement ? document.activeElement : null
            setUploadBlockedOpen(true)
            return
        }
        if (mobileOpen && changing) {
            navigationPendingRef.current = true
            onNavigationStart()
        }
        go(target, targetFamily)
        setMobileOpen(false)
    }

    return (
        <>
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
                <div className="sticky top-0 z-40 flex h-16 items-center justify-between gap-3 border-b border-border bg-background/80 px-5 backdrop-blur-md lg:hidden">
                    <div className="flex min-w-0 items-center gap-3">
                        <SheetTrigger asChild>
                            <Button variant="outline" size="icon" aria-label={t('nav.openMenu')}>
                                <MenuIcon />
                            </Button>
                        </SheetTrigger>
                        <Brand />
                    </div>
                    <ThemeToggle />
                </div>
                <SheetContent
                    side="left"
                    className="w-[min(20rem,calc(100vw-2rem))] max-w-none overflow-y-auto overscroll-contain p-5"
                    onCloseAutoFocus={(event) => {
                        if (navigationPendingRef.current) {
                            event.preventDefault()
                            navigationPendingRef.current = false
                            onNavigationComplete()
                        }
                    }}
                >
                    <SheetHeader className="p-0">
                        <SheetTitle asChild>
                            <div>
                                <Brand />
                            </div>
                        </SheetTitle>
                        <SheetDescription className="sr-only">
                            {t('nav.sheetHint')}
                        </SheetDescription>
                    </SheetHeader>
                    <NavigationBody onSelect={select} />
                    <div className="mt-auto">
                        <SidebarFooter />
                    </div>
                </SheetContent>
            </Sheet>

            <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 flex-col gap-6 border-r border-border bg-card p-5 lg:flex">
                <Brand />
                <div className="-mx-2 min-h-0 flex-1 overflow-y-auto px-2">
                    <NavigationBody onSelect={select} />
                </div>
                <SidebarFooter />
            </aside>

            <AlertDialog open={uploadBlockedOpen} onOpenChange={setUploadBlockedOpen}>
                <AlertDialogContent
                    onCloseAutoFocus={(event) => {
                        event.preventDefault()
                        const previous = blockedFocusRef.current
                        blockedFocusRef.current = null
                        if (previous?.isConnected) previous.focus()
                    }}
                >
                    <AlertDialogHeader>
                        <AlertDialogTitle>{t('upload.blocked.title')}</AlertDialogTitle>
                        <AlertDialogDescription>{t('upload.blocked.body')}</AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel variant="default">
                            {t('upload.blocked.stay')}
                        </AlertDialogCancel>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    )
}

export default SideBar
