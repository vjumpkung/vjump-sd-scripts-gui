import About from './about/about'
import Datasets from './components/datasets/datasets'
import Downloads from './components/downloads/downloads'
import Settings from './components/settings/settings'
import SideBar from './components/sidebar'
import TrainingWorkspace from './components/training/training_workspace'
import { Alert, AlertDescription } from './components/ui/alert'
import { Button } from './components/ui/button'
import useMenuBar from './hooks/useMenubar'
import { useSystemStatus } from './hooks/useSystem'
import { useI18n } from './i18n'
import { Suspense, lazy, useEffect, useRef } from 'react'

// The Jobs page pulls in xterm, so it loads on demand.
const LogViewer = lazy(() => import('./components/logs/logs'))

export default function App() {
    const { t } = useI18n()
    const page = useMenuBar((state) => state.page)
    const family = useMenuBar((state) => state.family)
    const go = useMenuBar((state) => state.go)
    const status = useSystemStatus()
    const mainRef = useRef<HTMLElement>(null)
    const previousRef = useRef(`${page}:${family}`)
    const navigationDeferredRef = useRef(false)

    // Move focus to the content after navigating, so keyboard and screen reader users land on it.
    useEffect(() => {
        const key = `${page}:${family}`
        if (previousRef.current === key) return
        previousRef.current = key
        if (!navigationDeferredRef.current) mainRef.current?.focus()
    }, [page, family])

    const schemaStale = status.data?.schema.stale === true && page !== 'settings'

    return (
        <div className="min-h-screen">
            <a
                href="#main-content"
                className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[80] focus:inline-flex focus:h-10 focus:items-center focus:rounded-full focus:bg-primary focus:px-4 focus:text-sm focus:font-medium focus:text-ink"
            >
                {t('app.skip')}
            </a>
            <SideBar
                onNavigationStart={() => {
                    navigationDeferredRef.current = true
                }}
                onNavigationComplete={() => {
                    navigationDeferredRef.current = false
                    mainRef.current?.focus()
                }}
            />
            <div className="lg:pl-72">
                <main
                    id="main-content"
                    ref={mainRef}
                    tabIndex={-1}
                    className="mx-auto w-full max-w-[88rem] px-5 py-10 outline-none sm:px-8 lg:py-14"
                >
                    {schemaStale ? (
                        <Alert className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                            <AlertDescription className="mt-0">
                                {t('env.stale.banner')}
                            </AlertDescription>
                            <Button variant="outline" onClick={() => go('settings')}>
                                {t('env.stale.action')}
                            </Button>
                        </Alert>
                    ) : null}
                    {page === 'training' ? <TrainingWorkspace /> : null}
                    {page === 'datasets' ? <Datasets /> : null}
                    {page === 'downloads' ? <Downloads /> : null}
                    {page === 'jobs' ? (
                        <Suspense
                            fallback={
                                <p className="py-10 text-sm text-muted-foreground">
                                    {t('common.loading')}
                                </p>
                            }
                        >
                            <LogViewer />
                        </Suspense>
                    ) : null}
                    {page === 'settings' ? <Settings /> : null}
                    {page === 'about' ? <About /> : null}
                </main>
            </div>
        </div>
    )
}
