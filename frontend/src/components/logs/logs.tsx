import SystemMonitor from './system_monitor'
import TerminalComponent, { type TerminalHandle } from './terminal'
import { queryKeys, trainingApi } from '@/api/api'
import { getApiErrorMessage } from '@/api/client'
import type { JobStatus, TrainingArtifact, TrainingJob } from '@/api/types'
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
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { useI18n } from '@/i18n'
import { clampPercent, formatBytes, formatDateTime, formatPercent } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    ArrowDownIcon,
    ArrowUpIcon,
    DownloadIcon,
    FileJsonIcon,
    PauseIcon,
    PlayIcon,
    RefreshCwIcon,
    SquareIcon,
    Trash2Icon
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

const ACTIVE: JobStatus[] = ['queued', 'running']
const POLL_ACTIVE_MS = 2_000
const POLL_IDLE_MS = 5_000
const LOG_POLL_MS = 2_000
// The backend serves logs in 64 KiB chunks; a full chunk means there is more to read right away.
const FULL_CHUNK = 60_000

// queued = muted, running = cyan, completed = yellow, failed = destructive outline, cancelled = muted
const STATUS_TONE = {
    queued: 'muted',
    running: 'cyan',
    completed: 'yellow',
    failed: 'destructive',
    cancelled: 'muted'
} as const

const JobStatusBadge = ({ status }: { status: JobStatus }) => {
    const { t } = useI18n()
    return <Badge variant={STATUS_TONE[status]}>{t(`status.${status}`)}</Badge>
}

const jobPercent = (job: TrainingJob) =>
    job.status === 'completed' ? 100 : clampPercent(job.progress?.percent)

type JobLogProps = { job: TrainingJob }

/**
 * Streams a job's log into the terminal. New content is appended with `terminal.write`; the
 * terminal is never reset and rewritten, so scrollback and text selection survive polling.
 */
const JobLog = ({ job }: JobLogProps) => {
    const { t } = useI18n()
    const terminal = useRef<TerminalHandle>(null)
    const [error, setError] = useState<string | null>(null)
    const [empty, setEmpty] = useState(true)
    // Read through a ref so changing the language does not restart the stream.
    const fallbackRef = useRef(t('jobs.logError'))
    fallbackRef.current = t('jobs.logError')

    useEffect(() => {
        let cancelled = false
        let timer: number | undefined
        let offset = 0

        terminal.current?.reset()
        setEmpty(true)
        setError(null)

        const poll = async () => {
            try {
                const chunk = await trainingApi.getLogs(job.id, offset)
                if (cancelled) return
                if (chunk.content) {
                    terminal.current?.write(chunk.content)
                    setEmpty(false)
                }
                offset = chunk.next_offset
                setError(null)
                if (chunk.eof) return
                timer = window.setTimeout(
                    poll,
                    chunk.content.length >= FULL_CHUNK ? 0 : LOG_POLL_MS
                )
            } catch (caught) {
                if (cancelled) return
                setError(getApiErrorMessage(caught, fallbackRef.current))
                timer = window.setTimeout(poll, LOG_POLL_MS)
            }
        }
        void poll()

        return () => {
            cancelled = true
            window.clearTimeout(timer)
        }
    }, [job.id])

    return (
        <div className="flex flex-col gap-3">
            {error ? (
                <p role="alert" className="text-sm text-destructive">
                    {error}
                </p>
            ) : null}
            <div className="relative">
                <TerminalComponent ref={terminal} label={t('jobs.logs')} />
                {empty ? (
                    <p className="pointer-events-none absolute top-6 left-6 font-mono text-[0.8125rem] text-code-fg/60">
                        {t('jobs.logsWaiting')}
                    </p>
                ) : null}
            </div>
        </div>
    )
}

const artifactLabel = (artifact: TrainingArtifact) =>
    artifact.name.replace(/\.(safetensors|ckpt|pt)$/i, '')

const LogViewer = () => {
    const { t, tag } = useI18n()
    const queryClient = useQueryClient()
    const [selectedId, setSelectedId] = useState('')
    const [cancelTarget, setCancelTarget] = useState<TrainingJob | null>(null)
    const [deleteTarget, setDeleteTarget] = useState<TrainingJob | null>(null)

    const jobsQuery = useQuery({
        queryKey: queryKeys.jobs,
        queryFn: trainingApi.listJobs,
        refetchInterval: (query) =>
            query.state.data?.some((job) => ACTIVE.includes(job.status))
                ? POLL_ACTIVE_MS
                : POLL_IDLE_MS
    })
    const queueQuery = useQuery({
        queryKey: queryKeys.queue,
        queryFn: trainingApi.getQueue,
        refetchInterval: POLL_ACTIVE_MS
    })

    const jobs = jobsQuery.data ?? []
    const selected =
        jobs.find((job) => job.id === selectedId) ??
        jobs.find((job) => job.status === 'running') ??
        jobs[0]
    const queued = jobs
        .filter((job) => job.status === 'queued')
        .sort((a, b) => (a.queue_position ?? 0) - (b.queue_position ?? 0))

    const artifactsQuery = useQuery({
        queryKey: queryKeys.artifacts(selected?.id ?? ''),
        queryFn: () => trainingApi.getArtifacts(selected?.id ?? ''),
        enabled: Boolean(selected),
        refetchInterval: selected?.status === 'running' ? POLL_IDLE_MS : false
    })
    const artifacts = artifactsQuery.data?.files ?? []

    // Re-read the artifacts whenever the selected job changes state.
    useEffect(() => {
        if (!selected) return
        void queryClient.invalidateQueries({ queryKey: queryKeys.artifacts(selected.id) })
    }, [queryClient, selected?.id, selected?.status])

    const refresh = async () => {
        await Promise.all([
            queryClient.invalidateQueries({ queryKey: queryKeys.jobs }),
            queryClient.invalidateQueries({ queryKey: queryKeys.queue })
        ])
    }

    const queueMutation = useMutation({
        mutationFn: () =>
            queueQuery.data?.state === 'running'
                ? trainingApi.pauseQueue()
                : trainingApi.startQueue(),
        onSuccess: (queue) => queryClient.setQueryData(queryKeys.queue, queue)
    })
    const cancelMutation = useMutation({
        mutationFn: trainingApi.cancel,
        onSuccess: () => {
            setCancelTarget(null)
            return refresh()
        },
        onError: () => setCancelTarget(null)
    })
    const retryMutation = useMutation({
        mutationFn: trainingApi.retry,
        onSuccess: async (job) => {
            setSelectedId(job.id)
            await refresh()
        }
    })
    const deleteMutation = useMutation({
        mutationFn: trainingApi.remove,
        onSuccess: async () => {
            setDeleteTarget(null)
            setSelectedId('')
            await refresh()
        },
        onError: () => setDeleteTarget(null)
    })
    const reorderMutation = useMutation({
        mutationFn: ({ id, position }: { id: string; position: number }) =>
            trainingApi.reorder(id, position),
        onSuccess: refresh
    })

    const error =
        jobsQuery.error ??
        queueQuery.error ??
        artifactsQuery.error ??
        queueMutation.error ??
        cancelMutation.error ??
        retryMutation.error ??
        deleteMutation.error ??
        reorderMutation.error
    const queueRunning = queueQuery.data?.state === 'running'

    const stepLabel = (job: TrainingJob) => {
        const progress = job.progress
        if (progress?.total_steps) {
            return t('jobs.steps', { step: progress.step ?? 0, total: progress.total_steps })
        }
        if (job.status === 'queued') return t('jobs.waitingQueue')
        if (job.status === 'running') return t('jobs.waitingSteps')
        if (job.status === 'completed') return t('jobs.complete')
        return t('jobs.stoppedEarly')
    }

    return (
        <div>
            <PageHeader
                before={t('jobs.title.before')}
                mark={t('jobs.title.mark')}
                description={t('jobs.subtitle')}
                actions={
                    <>
                        <div
                            role="status"
                            aria-live="polite"
                            aria-atomic="true"
                            className="text-right text-sm"
                        >
                            <p className="font-semibold">
                                {queueQuery.data
                                    ? queueRunning
                                        ? t('aside.queueRunning')
                                        : t('aside.queuePaused')
                                    : t('common.loading')}
                            </p>
                            <p className="text-muted-foreground">
                                {t('aside.waiting', { count: queueQuery.data?.queued ?? 0 })}
                            </p>
                        </div>
                        <Button
                            variant="default"
                            disabled={!queueQuery.data || queueMutation.isPending}
                            onClick={() => queueMutation.mutate()}
                        >
                            {queueRunning ? <PauseIcon /> : <PlayIcon />}
                            {queueRunning ? t('queue.pause') : t('queue.start')}
                        </Button>
                    </>
                }
            />

            {error ? (
                <Alert variant="destructive" className="mb-6">
                    <AlertDescription className="mt-0">
                        {getApiErrorMessage(error, t('jobs.requestFailed'))}
                    </AlertDescription>
                </Alert>
            ) : null}

            <SystemMonitor />

            <div className="grid gap-6 lg:grid-cols-[22rem_minmax(0,1fr)] lg:items-start">
                <Card compact className="lg:sticky lg:top-6">
                    <CardHeader className="mb-3 flex-row items-center justify-between">
                        <CardTitle className="text-lg">{t('jobs.list')}</CardTitle>
                        <span className="tabular text-sm text-muted-foreground">{jobs.length}</span>
                    </CardHeader>
                    <ul className="flex max-h-[70vh] flex-col overflow-y-auto">
                        {jobs.map((job) => {
                            const position = queued.findIndex((item) => item.id === job.id)
                            const isSelected = selected?.id === job.id
                            return (
                                <li
                                    key={job.id}
                                    className="flex items-stretch gap-1 border-b border-border last:border-b-0"
                                >
                                    <button
                                        type="button"
                                        aria-current={isSelected ? 'true' : undefined}
                                        className={cn(
                                            'min-w-0 flex-1 rounded-lg px-3 py-3 text-left transition-colors hover:bg-muted motion-reduce:transition-none',
                                            isSelected && 'bg-muted'
                                        )}
                                        onClick={() => setSelectedId(job.id)}
                                    >
                                        <div className="flex items-start justify-between gap-2">
                                            <span className="truncate font-semibold">
                                                {job.name}
                                            </span>
                                            <JobStatusBadge status={job.status} />
                                        </div>
                                        <p className="mt-1 truncate text-xs text-muted-foreground">
                                            <span translate="no">{job.preset_id}</span>
                                            {job.queue_position !== null
                                                ? ` · ${t('jobs.queuePosition', { position: job.queue_position + 1 })}`
                                                : ''}
                                        </p>
                                        {job.status === 'running' ? (
                                            <Progress
                                                aria-label={`${job.name} ${t('jobs.progress')}`}
                                                value={clampPercent(job.progress?.percent)}
                                                className="mt-2"
                                            />
                                        ) : null}
                                    </button>
                                    {job.status === 'queued' ? (
                                        <div className="flex items-center">
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                aria-label={t('jobs.moveUp')}
                                                title={t('jobs.moveUp')}
                                                disabled={
                                                    position <= 0 || reorderMutation.isPending
                                                }
                                                onClick={() =>
                                                    reorderMutation.mutate({
                                                        id: job.id,
                                                        position: (job.queue_position ?? 0) - 1
                                                    })
                                                }
                                            >
                                                <ArrowUpIcon />
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                aria-label={t('jobs.moveDown')}
                                                title={t('jobs.moveDown')}
                                                disabled={
                                                    position === -1 ||
                                                    position >= queued.length - 1 ||
                                                    reorderMutation.isPending
                                                }
                                                onClick={() =>
                                                    reorderMutation.mutate({
                                                        id: job.id,
                                                        position: (job.queue_position ?? 0) + 1
                                                    })
                                                }
                                            >
                                                <ArrowDownIcon />
                                            </Button>
                                        </div>
                                    ) : null}
                                </li>
                            )
                        })}
                        {!jobsQuery.isPending && jobs.length === 0 ? (
                            <li className="my-2 rounded-lg border border-dashed border-border px-3 py-10 text-center text-sm text-muted-foreground">
                                {t('jobs.empty')}
                            </li>
                        ) : null}
                    </ul>
                </Card>

                <div className="flex min-w-0 flex-col gap-6">
                    {selected ? (
                        <Card>
                            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                                <div className="min-w-0">
                                    <div className="flex flex-wrap items-center gap-3">
                                        <h2 className="text-xl leading-[1.4] font-bold break-words">
                                            {selected.name}
                                        </h2>
                                        <JobStatusBadge status={selected.status} />
                                    </div>
                                    <p className="mt-1 text-sm text-muted-foreground">
                                        {t('jobs.created', {
                                            time: formatDateTime(selected.created_at, tag)
                                        })}
                                    </p>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    {ACTIVE.includes(selected.status) ? (
                                        <Button
                                            variant="destructive"
                                            disabled={cancelMutation.isPending}
                                            onClick={() => setCancelTarget(selected)}
                                        >
                                            <SquareIcon />
                                            {t('common.cancel')}
                                        </Button>
                                    ) : null}
                                    {selected.status === 'failed' ||
                                    selected.status === 'cancelled' ? (
                                        <Button
                                            variant="outline"
                                            disabled={retryMutation.isPending}
                                            onClick={() => retryMutation.mutate(selected.id)}
                                        >
                                            <RefreshCwIcon />
                                            {t('common.retry')}
                                        </Button>
                                    ) : null}
                                    {!ACTIVE.includes(selected.status) ? (
                                        <Button
                                            variant="ghost"
                                            disabled={deleteMutation.isPending}
                                            onClick={() => setDeleteTarget(selected)}
                                        >
                                            <Trash2Icon />
                                            {t('common.delete')}
                                        </Button>
                                    ) : null}
                                </div>
                            </div>

                            <div className="mt-5 flex flex-col gap-3 rounded-lg border border-border p-4">
                                <div className="flex items-start justify-between gap-4">
                                    <div>
                                        <p className="text-sm font-semibold">
                                            {t('jobs.progress')}
                                        </p>
                                        <p className="mt-1 text-xs text-muted-foreground">
                                            {stepLabel(selected)}
                                            {selected.progress?.total_epochs
                                                ? ` · ${t('jobs.epochs', {
                                                      epoch: selected.progress.epoch ?? 0,
                                                      total: selected.progress.total_epochs
                                                  })}`
                                                : ''}
                                        </p>
                                    </div>
                                    <Badge variant="outline">
                                        {formatPercent(jobPercent(selected), tag)}
                                    </Badge>
                                </div>
                                <Progress
                                    aria-label={`${selected.name} ${t('jobs.progress')}`}
                                    aria-valuetext={stepLabel(selected)}
                                    value={jobPercent(selected)}
                                />
                            </div>

                            <div className="mt-4 flex flex-col gap-3 rounded-lg border border-border p-4">
                                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                                    <div>
                                        <p className="text-sm font-semibold">
                                            {t('jobs.artifacts')}
                                        </p>
                                        <p className="mt-0.5 text-xs text-muted-foreground">
                                            {artifactsQuery.isPending
                                                ? t('jobs.artifacts.checking')
                                                : t('jobs.artifacts.count', {
                                                      count: artifacts.length,
                                                      size: formatBytes(
                                                          artifactsQuery.data?.total_size_bytes ??
                                                              0,
                                                          tag
                                                      )
                                                  })}
                                        </p>
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                        <Button variant="outline" asChild>
                                            <a href={trainingApi.configUrl(selected.id)}>
                                                <FileJsonIcon />
                                                {t('jobs.configDownload')}
                                            </a>
                                        </Button>
                                        {artifacts.length > 0 ? (
                                            <Button variant="default" asChild>
                                                <a href={trainingApi.artifactsZipUrl(selected.id)}>
                                                    <DownloadIcon />
                                                    {t('jobs.downloadAll')}
                                                </a>
                                            </Button>
                                        ) : (
                                            <Button variant="default" disabled>
                                                <DownloadIcon />
                                                {t('jobs.downloadAll')}
                                            </Button>
                                        )}
                                    </div>
                                </div>
                                {artifacts.length > 0 ? (
                                    <ul className="flex flex-col border-t border-border">
                                        {artifacts.map((artifact) => (
                                            <li
                                                key={artifact.name}
                                                className="flex items-center justify-between gap-3 border-b border-border py-2 last:border-b-0"
                                            >
                                                <div className="flex min-w-0 items-center gap-2">
                                                    <Badge variant="outline">
                                                        {t(`jobs.artifact.${artifact.kind}`)}
                                                    </Badge>
                                                    <span
                                                        className="truncate font-mono text-sm"
                                                        title={artifact.name}
                                                        translate="no"
                                                    >
                                                        {artifactLabel(artifact)}
                                                    </span>
                                                </div>
                                                <div className="flex shrink-0 items-center gap-2">
                                                    <span className="tabular text-xs text-muted-foreground">
                                                        {formatBytes(artifact.size_bytes, tag)}
                                                    </span>
                                                    <Button variant="ghost" size="icon" asChild>
                                                        <a
                                                            href={trainingApi.artifactUrl(
                                                                selected.id,
                                                                artifact.name
                                                            )}
                                                            aria-label={`${t('jobs.download')} ${artifact.name}`}
                                                            title={t('jobs.download')}
                                                        >
                                                            <DownloadIcon />
                                                        </a>
                                                    </Button>
                                                </div>
                                            </li>
                                        ))}
                                    </ul>
                                ) : null}
                            </div>

                            {selected.error ? (
                                <Alert variant="destructive" className="mt-4">
                                    <pre className="font-mono text-xs break-words whitespace-pre-wrap">
                                        {selected.error}
                                    </pre>
                                </Alert>
                            ) : null}
                        </Card>
                    ) : null}

                    <Card compact className="overflow-hidden">
                        <CardHeader className="mb-3">
                            <CardTitle className="text-lg">{t('jobs.logs')}</CardTitle>
                            <CardDescription>
                                {selected ? selected.name : t('jobs.logsNone')}
                            </CardDescription>
                        </CardHeader>
                        {selected ? (
                            <JobLog key={selected.id} job={selected} />
                        ) : (
                            <p className="rounded-xl border border-dashed border-border px-4 py-12 text-center text-sm text-muted-foreground">
                                {t('jobs.logsNone')}
                            </p>
                        )}
                    </Card>
                </div>
            </div>

            <AlertDialog
                open={cancelTarget !== null}
                onOpenChange={(open) => !open && setCancelTarget(null)}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>{t('jobs.cancel.title')}</AlertDialogTitle>
                        <AlertDialogDescription>
                            {t('jobs.cancel.body', { name: cancelTarget?.name ?? '' })}
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>{t('jobs.cancel.keep')}</AlertDialogCancel>
                        <AlertDialogAction
                            variant="destructive"
                            disabled={cancelMutation.isPending}
                            onClick={(event) => {
                                event.preventDefault()
                                if (cancelTarget) cancelMutation.mutate(cancelTarget.id)
                            }}
                        >
                            {t('jobs.cancel.confirm')}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog
                open={deleteTarget !== null}
                onOpenChange={(open) => !open && setDeleteTarget(null)}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>{t('jobs.delete.title')}</AlertDialogTitle>
                        <AlertDialogDescription>
                            {t('jobs.delete.body', { name: deleteTarget?.name ?? '' })}
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                        <AlertDialogAction
                            variant="destructive"
                            disabled={deleteMutation.isPending}
                            onClick={(event) => {
                                event.preventDefault()
                                if (deleteTarget) deleteMutation.mutate(deleteTarget.id)
                            }}
                        >
                            {t('common.delete')}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    )
}

export default LogViewer
