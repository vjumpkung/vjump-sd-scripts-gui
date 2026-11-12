import { downloadsApi, queryKeys } from '@/api/api'
import { getApiErrorMessage } from '@/api/client'
import type { CatalogEntry, DownloadJob, JobStatus } from '@/api/types'
import PageHeader from '@/components/page_header'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle
} from '@/components/ui/alert-dialog'
import { Badge, type badgeVariants } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Chip } from '@/components/ui/chip'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import useMenuBar from '@/hooks/useMenubar'
import { useSystemStatus } from '@/hooks/useSystem'
import { useI18n } from '@/i18n'
import { clampPercent, formatBytes, formatGB, formatPercent } from '@/lib/format'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type VariantProps } from 'class-variance-authority'
import {
    CircleAlertIcon,
    CircleCheckIcon,
    CircleDashedIcon,
    DownloadIcon,
    RefreshCwIcon,
    SearchIcon,
    SquareIcon
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

const ACTIVE: JobStatus[] = ['queued', 'running']
const POLL_MS = 1_500
const ALL = '__all__'

const isActive = (job?: DownloadJob) => Boolean(job && ACTIVE.includes(job.status))

type Tone = NonNullable<VariantProps<typeof badgeVariants>['variant']>

const TONES: Tone[] = ['cyan', 'yellow', 'pink']

// Each family keeps one highlighter tone everywhere it appears.
const familyTone = (family: string): Tone =>
    TONES[[...family].reduce((sum, char) => sum + char.charCodeAt(0), 0) % TONES.length]

const STATUS_TONE: Record<JobStatus, Tone> = {
    queued: 'muted',
    running: 'cyan',
    completed: 'yellow',
    failed: 'destructive',
    cancelled: 'muted'
}

type DownloadCardProps = {
    entry: CatalogEntry
    job?: DownloadJob
    starting: boolean
    cancelling: boolean
    hfTokenMissing: boolean
    onStart: (entry: CatalogEntry) => void
    onCancel: (entry: CatalogEntry, job: DownloadJob) => void
}

const DownloadCard = ({
    entry,
    job,
    starting,
    cancelling,
    hfTokenMissing,
    onStart,
    onCancel
}: DownloadCardProps) => {
    const { t, lookup, tag } = useI18n()
    const go = useMenuBar((state) => state.go)
    const active = isActive(job)
    const present = entry.files.filter((file) => file.present).length
    const complete = present === entry.files.length
    const retry = job?.status === 'failed' || job?.status === 'cancelled'

    return (
        <Card>
            <article className="flex flex-col gap-4">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                    <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                            <h2 className="text-xl leading-[1.4] font-bold" translate="no">
                                {entry.name}
                            </h2>
                            <Badge variant={familyTone(entry.family)}>
                                {lookup(`family.${entry.family}`) ?? entry.family}
                            </Badge>
                            {entry.gated ? (
                                <Badge variant="outline">{t('downloads.gated')}</Badge>
                            ) : null}
                            {complete ? (
                                <Badge variant="cyan">{t('downloads.installed')}</Badge>
                            ) : null}
                            {job ? (
                                <Badge variant={STATUS_TONE[job.status]}>
                                    {t(`status.${job.status}`)}
                                </Badge>
                            ) : null}
                        </div>
                        <p className="tabular mt-2 text-sm text-muted-foreground">
                            {t('downloads.size', { size: formatGB(entry.size_bytes, tag) })}
                            {' · '}
                            {t('downloads.filesPresent', { present, total: entry.files.length })}
                        </p>
                    </div>

                    <div className="flex shrink-0 gap-2">
                        {active && job ? (
                            <Button
                                variant="destructive"
                                disabled={cancelling}
                                aria-label={`${t('common.cancel')} ${entry.name}`}
                                onClick={() => onCancel(entry, job)}
                            >
                                <SquareIcon />
                                {t('common.cancel')}
                            </Button>
                        ) : (
                            <Button
                                variant={complete ? 'outline' : 'default'}
                                disabled={starting || complete}
                                aria-label={`${retry ? t('common.retry') : t('downloads.download')} ${entry.name}`}
                                onClick={() => onStart(entry)}
                            >
                                {retry ? <RefreshCwIcon /> : <DownloadIcon />}
                                {starting
                                    ? t('downloads.starting')
                                    : retry
                                      ? t('common.retry')
                                      : t('downloads.download')}
                            </Button>
                        )}
                    </div>
                </div>

                <ul className="flex flex-col border-t border-border">
                    {entry.files.map((file) => (
                        <li
                            key={file.path}
                            className="flex items-center gap-3 border-b border-border py-2 text-sm last:border-b-0"
                        >
                            {file.present ? (
                                <CircleCheckIcon aria-hidden className="size-4 shrink-0" />
                            ) : (
                                <CircleDashedIcon
                                    aria-hidden
                                    className="size-4 shrink-0 text-muted-foreground"
                                />
                            )}
                            <span
                                className="min-w-0 flex-1 font-mono text-[0.8125rem] break-all"
                                translate="no"
                            >
                                {file.path}
                            </span>
                            <span className="tabular shrink-0 text-xs text-muted-foreground">
                                {formatBytes(file.size_bytes, tag)}
                            </span>
                            <span className="sr-only">
                                {file.present ? t('downloads.present') : t('downloads.missing')}
                            </span>
                            <Badge variant={file.present ? 'outline' : 'muted'} aria-hidden>
                                {file.present ? t('downloads.present') : t('downloads.missing')}
                            </Badge>
                        </li>
                    ))}
                </ul>

                {entry.gated && hfTokenMissing && !complete ? (
                    <Alert>
                        <AlertDescription className="mt-0">
                            {t('downloads.gatedNote')}{' '}
                            <Button variant="link" onClick={() => go('settings')}>
                                {t('downloads.openSettings')}
                            </Button>
                        </AlertDescription>
                    </Alert>
                ) : null}

                {job && (active || job.status === 'running') ? (
                    <div className="flex flex-col gap-2">
                        <Progress
                            value={clampPercent(job.progress)}
                            aria-label={`${entry.name} ${t('downloads.progress')}`}
                        />
                        <div className="tabular flex items-center justify-between gap-3 text-xs text-muted-foreground">
                            <span
                                className="min-w-0 truncate font-mono"
                                title={job.current_file ?? ''}
                                translate="no"
                            >
                                {job.current_file ?? t('downloads.preparing')}
                            </span>
                            <span className="shrink-0">
                                {formatPercent(job.progress, tag, 1)}
                                {job.total_bytes
                                    ? ` · ${formatBytes(job.downloaded_bytes, tag)} / ${formatBytes(job.total_bytes, tag)}`
                                    : ''}
                            </span>
                        </div>
                    </div>
                ) : null}
                {job?.error ? (
                    <p role="alert" className="flex items-start gap-2 text-sm text-destructive">
                        <CircleAlertIcon className="mt-0.5 size-4 shrink-0" />
                        <span>{job.error}</span>
                    </p>
                ) : null}
            </article>
        </Card>
    )
}

const Downloads = () => {
    const { t, lookup } = useI18n()
    const queryClient = useQueryClient()
    const status = useSystemStatus()
    const [family, setFamily] = useState(ALL)
    const [search, setSearch] = useState('')
    const [cancelTarget, setCancelTarget] = useState<{
        entry: CatalogEntry
        job: DownloadJob
    } | null>(null)

    // Poll only while something is downloading, then once more so presence flags catch up.
    const downloadsQuery = useQuery({
        queryKey: queryKeys.downloads,
        queryFn: downloadsApi.list,
        refetchOnMount: 'always',
        refetchInterval: (query) =>
            query.state.data?.some((job) => isActive(job)) ? POLL_MS : false
    })
    const jobsList = downloadsQuery.data
    const anyActive = Boolean(jobsList?.some((job) => isActive(job)))

    const catalogQuery = useQuery({
        queryKey: queryKeys.catalog,
        queryFn: downloadsApi.catalog,
        refetchOnMount: 'always',
        refetchInterval: anyActive ? 4_000 : false
    })

    const wasActive = useRef(false)
    useEffect(() => {
        if (wasActive.current && !anyActive) {
            void queryClient.invalidateQueries({ queryKey: queryKeys.catalog })
        }
        wasActive.current = anyActive
    }, [anyActive, queryClient])

    const catalog = catalogQuery.data ?? []
    const families = useMemo(() => [...new Set(catalog.map((entry) => entry.family))], [catalog])
    const jobsByModel = useMemo(() => {
        // The list is newest first, so the first job seen for a model is its latest.
        const map = new Map<string, DownloadJob>()
        for (const job of jobsList ?? []) if (!map.has(job.model_id)) map.set(job.model_id, job)
        return map
    }, [jobsList])

    const needle = search.trim().toLowerCase()
    const visible = catalog.filter(
        (entry) =>
            (family === ALL || entry.family === family) &&
            (!needle ||
                [entry.name, entry.family, entry.id, lookup(`family.${entry.family}`) ?? ''].some(
                    (text) => text.toLowerCase().includes(needle)
                ))
    )

    const startMutation = useMutation({
        mutationFn: (entry: CatalogEntry) => downloadsApi.start(entry.id),
        onSuccess: (job) =>
            queryClient.setQueryData<DownloadJob[]>(queryKeys.downloads, (current) => [
                job,
                ...(current ?? []).filter((item) => item.id !== job.id)
            ])
    })
    const cancelMutation = useMutation({
        mutationFn: (job: DownloadJob) => downloadsApi.cancel(job.id),
        onSuccess: (job) =>
            queryClient.setQueryData<DownloadJob[]>(queryKeys.downloads, (current) =>
                (current ?? []).map((item) => (item.id === job.id ? job : item))
            ),
        onSettled: () => setCancelTarget(null)
    })

    const error =
        catalogQuery.error ?? downloadsQuery.error ?? startMutation.error ?? cancelMutation.error

    return (
        <div>
            <PageHeader
                before={t('downloads.title.before')}
                mark={t('downloads.title.mark')}
                description={t('downloads.subtitle')}
            />

            <div className="mb-6 flex flex-col gap-4">
                <div className="relative max-w-md">
                    <SearchIcon
                        aria-hidden
                        className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
                    />
                    <Input
                        type="search"
                        value={search}
                        placeholder={t('downloads.search')}
                        aria-label={t('downloads.search')}
                        autoComplete="off"
                        className="h-11 pl-10"
                        onChange={(event) => setSearch(event.target.value)}
                    />
                </div>
                <div
                    role="group"
                    aria-label={t('downloads.filter')}
                    className="flex flex-wrap gap-2"
                >
                    <Chip active={family === ALL} onClick={() => setFamily(ALL)}>
                        {t('downloads.all')}
                    </Chip>
                    {families.map((id) => (
                        <Chip key={id} active={family === id} onClick={() => setFamily(id)}>
                            {lookup(`family.${id}`) ?? id}
                        </Chip>
                    ))}
                </div>
            </div>

            {error ? (
                <Alert variant="destructive" className="mb-6">
                    <AlertDescription className="mt-0">
                        {getApiErrorMessage(error, t('downloads.error'))}
                    </AlertDescription>
                </Alert>
            ) : null}

            <section className="grid gap-4" aria-label={t('downloads.title.mark')}>
                {visible.map((entry) => {
                    const job = jobsByModel.get(entry.id)
                    return (
                        <DownloadCard
                            key={entry.id}
                            entry={entry}
                            job={job}
                            starting={
                                startMutation.isPending && startMutation.variables?.id === entry.id
                            }
                            cancelling={
                                cancelMutation.isPending && cancelMutation.variables?.id === job?.id
                            }
                            hfTokenMissing={status.data?.secrets.hf_token === false}
                            onStart={(item) => startMutation.mutate(item)}
                            onCancel={(item, target) =>
                                setCancelTarget({ entry: item, job: target })
                            }
                        />
                    )
                })}
            </section>

            {!catalogQuery.isPending && visible.length === 0 ? (
                <p className="rounded-xl border border-dashed border-border px-6 py-16 text-center text-sm text-muted-foreground">
                    {t('downloads.empty')}
                </p>
            ) : null}

            <AlertDialog
                open={cancelTarget !== null}
                onOpenChange={(open) => !open && setCancelTarget(null)}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>{t('downloads.cancel.title')}</AlertDialogTitle>
                        <AlertDialogDescription>
                            {t('downloads.cancel.body', { name: cancelTarget?.entry.name ?? '' })}
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>{t('downloads.cancel.keep')}</AlertDialogCancel>
                        <AlertDialogAction
                            variant="destructive"
                            disabled={cancelMutation.isPending}
                            onClick={(event) => {
                                event.preventDefault()
                                if (cancelTarget) cancelMutation.mutate(cancelTarget.job)
                            }}
                        >
                            {t('downloads.cancel.confirm')}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    )
}

export default Downloads
