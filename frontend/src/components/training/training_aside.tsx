import { queryKeys, trainingApi } from '@/api/api'
import { getApiErrorMessage } from '@/api/client'
import type { JobRequest, Preset, TrainingJob } from '@/api/types'
import { CodeBlock, copyText } from '@/components/code_block'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import useDebounced from '@/hooks/useDebounced'
import useMenuBar from '@/hooks/useMenubar'
import { useI18n } from '@/i18n'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    CircleCheckIcon,
    CircleIcon,
    ClipboardIcon,
    DownloadIcon,
    PauseIcon,
    PlayIcon,
    RocketIcon,
    RotateCcwIcon,
    UploadIcon
} from 'lucide-react'
import { type ChangeEvent, useRef, useState } from 'react'

export type ReadinessItem = { id: string; label: string; ok: boolean }

export type ImportStatus = { kind: 'ok' | 'error'; message: string }

type TrainingAsideProps = {
    preset: Preset
    request: JobRequest
    readiness: ReadinessItem[]
    ready: boolean
    acceleratePreview: string
    importStatus: ImportStatus | null
    onExport: () => void
    onImportFile: (file: File) => void
    onRestoreDefaults: () => void
}

const TrainingAside = ({
    preset,
    request,
    readiness,
    ready,
    acceleratePreview,
    importStatus,
    onExport,
    onImportFile,
    onRestoreDefaults
}: TrainingAsideProps) => {
    const { t, lookup } = useI18n()
    const queryClient = useQueryClient()
    const go = useMenuBar((state) => state.go)
    const importRef = useRef<HTMLInputElement>(null)
    const [added, setAdded] = useState<TrainingJob | null>(null)
    const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle')

    const requestJson = JSON.stringify(request)
    const debouncedJson = useDebounced(requestJson, 400)
    const preview = useQuery({
        queryKey: ['training', 'preview', debouncedJson] as const,
        queryFn: () => trainingApi.preview(JSON.parse(debouncedJson) as JobRequest),
        placeholderData: keepPreviousData,
        retry: false,
        staleTime: 5_000
    })

    const queue = useQuery({
        queryKey: queryKeys.queue,
        queryFn: trainingApi.getQueue,
        refetchInterval: 1_500
    })

    const queueMutation = useMutation({
        mutationFn: () =>
            queue.data?.state === 'running' ? trainingApi.pauseQueue() : trainingApi.startQueue(),
        onSuccess: (next) => queryClient.setQueryData(queryKeys.queue, next)
    })

    const addMutation = useMutation({
        mutationFn: () => trainingApi.createJob(request),
        onSuccess: (job) => {
            setAdded(job)
            void queryClient.invalidateQueries({ queryKey: queryKeys.jobs })
            void queryClient.invalidateQueries({ queryKey: queryKeys.queue })
        }
    })

    const copyCommand = async () => {
        if (!preview.data?.command) return
        setCopyState((await copyText(preview.data.command)) ? 'copied' : 'failed')
        window.setTimeout(() => setCopyState('idle'), 1_800)
    }

    const handleImport = (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        if (file) onImportFile(file)
        event.target.value = ''
    }

    const queueRunning = queue.data?.state === 'running'
    const previewErrors = preview.data?.errors ?? []
    const stale = requestJson !== debouncedJson || preview.isFetching
    const missing = readiness.filter((item) => !item.ok)
    const queueName = queue.data
        ? queueRunning
            ? t('aside.queueRunning')
            : t('aside.queuePaused')
        : t('common.loading')

    return (
        <aside
            aria-label={t('aside.title')}
            className="flex min-w-0 flex-col gap-4 xl:sticky xl:top-6 xl:max-h-[calc(100dvh-3rem)] xl:overflow-y-auto xl:pr-1"
        >
            <Card compact>
                <CardHeader className="mb-4">
                    <CardTitle className="text-lg">{t('aside.readiness')}</CardTitle>
                </CardHeader>
                <ul className="flex flex-col gap-1">
                    {readiness.map((item) => (
                        <li key={item.id} className="flex min-h-8 items-start gap-3 text-sm">
                            {item.ok ? (
                                <CircleCheckIcon aria-hidden className="mt-0.5 size-4 shrink-0" />
                            ) : (
                                <CircleIcon
                                    aria-hidden
                                    className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                                />
                            )}
                            <span className={item.ok ? 'text-foreground' : 'text-muted-foreground'}>
                                {item.label}
                                <span className="sr-only">
                                    {' '}
                                    {item.ok ? t('aside.done') : t('aside.todo')}
                                </span>
                            </span>
                        </li>
                    ))}
                </ul>
                <p className="mt-3 text-sm font-medium" role="status" aria-live="polite">
                    {ready ? t('aside.ready') : t('aside.notReady', { count: missing.length })}
                </p>
            </Card>

            <Card compact>
                <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                        <p className="text-sm font-semibold">{t('aside.queue')}</p>
                        <p
                            className="text-sm text-muted-foreground"
                            role="status"
                            aria-live="polite"
                        >
                            {queueName}
                            {queue.data
                                ? ` · ${t('aside.waiting', { count: queue.data.queued })}`
                                : ''}
                        </p>
                    </div>
                    <Button
                        variant="outline"
                        disabled={!queue.data || queueMutation.isPending}
                        onClick={() => queueMutation.mutate()}
                    >
                        {queueRunning ? <PauseIcon /> : <PlayIcon />}
                        {queueRunning ? t('queue.pause') : t('queue.start')}
                    </Button>
                </div>
                {queueMutation.error ? (
                    <p role="alert" className="mt-3 text-sm text-destructive">
                        {getApiErrorMessage(queueMutation.error, t('queue.error'))}
                    </p>
                ) : null}
            </Card>

            <Card compact>
                <CardHeader className="mb-3">
                    <div className="flex items-center justify-between gap-3">
                        <CardTitle className="text-lg">{t('aside.preview')}</CardTitle>
                        {stale ? <Badge variant="muted">{t('aside.updating')}</Badge> : null}
                    </div>
                </CardHeader>
                <CodeBlock
                    code={preview.data?.command ?? ''}
                    copyLabel={t('aside.copyCommand')}
                    placeholder={
                        preview.isError ? t('aside.previewError') : t('aside.previewPlaceholder')
                    }
                />
                {preview.isError ? (
                    <p role="alert" className="mt-3 text-sm text-destructive">
                        {getApiErrorMessage(preview.error, t('aside.previewError'))}
                    </p>
                ) : null}
                {previewErrors.length > 0 ? (
                    <Alert variant="destructive" className="mt-3 px-4 py-3">
                        <AlertTitle>{t('aside.previewErrors')}</AlertTitle>
                        <AlertDescription>
                            <ul className="list-disc pl-5">
                                {previewErrors.map((message) => (
                                    <li key={message}>{message}</li>
                                ))}
                            </ul>
                        </AlertDescription>
                    </Alert>
                ) : null}
                <p className="mt-3 text-[0.8125rem] leading-relaxed text-muted-foreground">
                    {acceleratePreview}{' '}
                    <Button variant="link" onClick={() => go('settings')}>
                        {t('aside.changeAccelerate')}
                    </Button>
                </p>
            </Card>

            <Card compact className="flex flex-col gap-3">
                <Button
                    variant="default"
                    size="lg"
                    disabled={!ready || addMutation.isPending}
                    onClick={() => {
                        setAdded(null)
                        addMutation.mutate()
                    }}
                >
                    <RocketIcon />
                    {addMutation.isPending ? t('aside.adding') : t('aside.add')}
                </Button>
                <Button
                    variant="outline"
                    disabled={!preview.data?.command}
                    onClick={() => void copyCommand()}
                >
                    <ClipboardIcon />
                    {copyState === 'copied'
                        ? t('common.copied')
                        : copyState === 'failed'
                          ? t('common.copyFailed')
                          : t('aside.copyCommand')}
                </Button>

                {addMutation.error ? (
                    <Alert variant="destructive">
                        <AlertTitle>{t('aside.addFailed')}</AlertTitle>
                        <AlertDescription>
                            {getApiErrorMessage(addMutation.error, t('aside.addFailed'))}
                        </AlertDescription>
                    </Alert>
                ) : null}
                {added ? (
                    <Alert>
                        <AlertTitle>{t('aside.added', { name: added.name })}</AlertTitle>
                        <AlertDescription>
                            <Button variant="link" onClick={() => go('jobs')}>
                                {t('aside.openJobs')}
                            </Button>
                        </AlertDescription>
                    </Alert>
                ) : null}

                <div className="flex flex-wrap gap-2 border-t border-border pt-3">
                    <input
                        ref={importRef}
                        type="file"
                        accept="application/json,.json"
                        className="hidden"
                        onChange={handleImport}
                    />
                    <Button variant="outline" onClick={() => importRef.current?.click()}>
                        <UploadIcon />
                        {t('aside.import')}
                    </Button>
                    <Button variant="outline" onClick={onExport}>
                        <DownloadIcon />
                        {t('aside.export')}
                    </Button>
                    <AlertDialog>
                        <AlertDialogTrigger asChild>
                            <Button variant="outline">
                                <RotateCcwIcon />
                                {t('aside.restore')}
                            </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                            <AlertDialogHeader>
                                <AlertDialogTitle>{t('aside.restore.title')}</AlertDialogTitle>
                                <AlertDialogDescription>
                                    {t('aside.restore.body', {
                                        preset: lookup(`presets.${preset.id}.name`) ?? preset.id
                                    })}
                                </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                                <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                                <AlertDialogAction
                                    variant="destructive"
                                    onClick={onRestoreDefaults}
                                >
                                    {t('aside.restore')}
                                </AlertDialogAction>
                            </AlertDialogFooter>
                        </AlertDialogContent>
                    </AlertDialog>
                </div>
                {importStatus ? (
                    <p
                        role={importStatus.kind === 'error' ? 'alert' : 'status'}
                        className={
                            importStatus.kind === 'error'
                                ? 'text-sm text-destructive'
                                : 'text-sm text-muted-foreground'
                        }
                    >
                        {importStatus.message}
                    </p>
                ) : null}
                <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">
                    {t('aside.draftNote')}
                </p>
            </Card>
        </aside>
    )
}

export default TrainingAside
