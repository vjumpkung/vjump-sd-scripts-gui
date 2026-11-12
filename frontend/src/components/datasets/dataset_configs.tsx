import DatasetEditor from './dataset_editor'
import { datasetsApi, queryKeys } from '@/api/api'
import { getApiErrorMessage } from '@/api/client'
import type { DatasetConfig, DatasetSummary, ValidateReport } from '@/api/types'
import { kindTone } from '@/components/kind_tone'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
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
import { Card } from '@/components/ui/card'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle
} from '@/components/ui/dialog'
import { useI18n } from '@/i18n'
import { formatDateTime } from '@/lib/format'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    CircleCheckIcon,
    CircleXIcon,
    DownloadIcon,
    ListChecksIcon,
    PencilIcon,
    PlusIcon,
    Trash2Icon,
    UploadIcon
} from 'lucide-react'
import { type ChangeEvent, useRef, useState } from 'react'

type ValidationDialogProps = {
    report: ValidateReport | null
    name: string
    onClose: () => void
}

const ValidationDialog = ({ report, name, onClose }: ValidationDialogProps) => {
    const { t } = useI18n()

    return (
        <Dialog open={report !== null} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-3xl">
                <DialogHeader>
                    <DialogTitle>{t('dataset.validate.title', { name })}</DialogTitle>
                    <DialogDescription>{t('dataset.validate.desc')}</DialogDescription>
                </DialogHeader>
                {report ? (
                    <div className="flex flex-col gap-4">
                        <Alert variant={report.ok ? 'note' : 'destructive'}>
                            <AlertTitle>
                                {report.ok ? t('dataset.validate.ok') : t('dataset.validate.notOk')}
                            </AlertTitle>
                        </Alert>
                        {report.datasets.map((dataset) => (
                            <section key={dataset.index} className="flex flex-col gap-2">
                                <h3 className="text-base font-semibold">
                                    {t('dataset.datasetN', { n: dataset.index + 1 })}
                                </h3>
                                <ul className="flex flex-col rounded-lg border border-border">
                                    {dataset.subsets.map((subset) => (
                                        <li
                                            key={subset.index}
                                            className="flex flex-col gap-2 border-b border-border p-4 last:border-b-0"
                                        >
                                            <div className="flex flex-wrap items-center gap-2">
                                                <Badge variant={kindTone[subset.kind]}>
                                                    {t(`kind.${subset.kind}`)}
                                                </Badge>
                                                <span className="text-sm font-medium">
                                                    {t('dataset.subsetN', { n: subset.index + 1 })}
                                                </span>
                                                {subset.exists ? (
                                                    <CircleCheckIcon
                                                        aria-label={t('dataset.validate.exists')}
                                                        className="size-4"
                                                    />
                                                ) : (
                                                    <CircleXIcon
                                                        aria-label={t('dataset.validate.missing')}
                                                        className="size-4 text-destructive"
                                                    />
                                                )}
                                            </div>
                                            <code
                                                className="font-mono text-[0.8125rem] break-all text-muted-foreground"
                                                translate="no"
                                            >
                                                {subset.path}
                                            </code>
                                            <p className="tabular text-sm">
                                                {t('dataset.validate.counts', {
                                                    images: subset.images,
                                                    captions: subset.captions
                                                })}
                                            </p>
                                            {subset.missing_captions.length > 0 ? (
                                                <div className="text-sm">
                                                    <p className="font-medium">
                                                        {t('dataset.validate.missingCaptions', {
                                                            count: subset.missing_captions.length
                                                        })}
                                                    </p>
                                                    <p
                                                        className="font-mono text-[0.8125rem] break-all text-muted-foreground"
                                                        translate="no"
                                                    >
                                                        {subset.missing_captions.join(', ')}
                                                    </p>
                                                </div>
                                            ) : null}
                                        </li>
                                    ))}
                                </ul>
                            </section>
                        ))}
                    </div>
                ) : null}
            </DialogContent>
        </Dialog>
    )
}

const DatasetConfigs = () => {
    const { t, tag } = useI18n()
    const queryClient = useQueryClient()
    const importRef = useRef<HTMLInputElement>(null)
    // undefined: closed, null: new config, string: edit that config.
    const [editing, setEditing] = useState<string | null | undefined>(undefined)
    const [deleteTarget, setDeleteTarget] = useState<DatasetSummary | null>(null)
    const [report, setReport] = useState<{ report: ValidateReport; name: string } | null>(null)
    const [saved, setSaved] = useState<DatasetConfig | null>(null)

    const listQuery = useQuery({ queryKey: queryKeys.datasets, queryFn: datasetsApi.list })
    const datasets = listQuery.data ?? []

    const importMutation = useMutation({
        mutationFn: (file: File) => datasetsApi.import(file),
        onSuccess: async (config) => {
            setSaved(config)
            await queryClient.invalidateQueries({ queryKey: queryKeys.datasets })
        }
    })
    const validateMutation = useMutation({
        mutationFn: (dataset: DatasetSummary) => datasetsApi.validate(dataset.id),
        onSuccess: (result, dataset) => setReport({ report: result, name: dataset.name })
    })
    const deleteMutation = useMutation({
        mutationFn: (dataset: DatasetSummary) => datasetsApi.remove(dataset.id),
        onSuccess: async () => {
            setDeleteTarget(null)
            await queryClient.invalidateQueries({ queryKey: queryKeys.datasets })
        },
        onError: () => setDeleteTarget(null)
    })

    const handleImport = (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        if (file) importMutation.mutate(file)
        event.target.value = ''
    }

    const error =
        listQuery.error ?? importMutation.error ?? validateMutation.error ?? deleteMutation.error

    return (
        <div className="flex flex-col gap-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="max-w-[42rem] text-[0.9375rem] leading-[1.65] text-muted-foreground">
                    {t('dataset.configs.desc')}
                </p>
                <div className="flex flex-wrap gap-2">
                    <input
                        ref={importRef}
                        type="file"
                        accept=".toml,application/toml"
                        className="hidden"
                        onChange={handleImport}
                    />
                    <Button
                        variant="outline"
                        disabled={importMutation.isPending}
                        onClick={() => importRef.current?.click()}
                    >
                        <UploadIcon />
                        {t('dataset.import')}
                    </Button>
                    <Button variant="default" onClick={() => setEditing(null)}>
                        <PlusIcon />
                        {t('dataset.new')}
                    </Button>
                </div>
            </div>

            {error ? (
                <Alert variant="destructive">
                    <AlertDescription className="mt-0">
                        {getApiErrorMessage(error, t('dataset.requestError'))}
                    </AlertDescription>
                </Alert>
            ) : null}

            {saved ? (
                <Alert>
                    <AlertTitle>{t('dataset.saved', { name: saved.name })}</AlertTitle>
                    {saved.warnings.length > 0 ? (
                        <AlertDescription>
                            <p className="font-medium">{t('dataset.warnings')}</p>
                            <ul className="list-disc pl-5">
                                {saved.warnings.map((warning) => (
                                    <li key={warning}>{warning}</li>
                                ))}
                            </ul>
                        </AlertDescription>
                    ) : null}
                </Alert>
            ) : null}

            {!listQuery.isPending && datasets.length === 0 ? (
                <p className="rounded-xl border border-dashed border-border px-6 py-16 text-center text-sm text-muted-foreground">
                    {t('dataset.empty')}
                </p>
            ) : (
                <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
                    {datasets.map((dataset) => (
                        <Card key={dataset.id} compact className="flex flex-col gap-4">
                            <div className="flex flex-col gap-2">
                                <h3 className="text-lg leading-[1.4] font-bold break-words">
                                    {dataset.name}
                                </h3>
                                <div className="flex flex-wrap gap-2">
                                    {dataset.kinds.map((kind) => (
                                        <Badge key={kind} variant={kindTone[kind]}>
                                            {t(`kind.${kind}`)}
                                        </Badge>
                                    ))}
                                </div>
                                {dataset.description ? (
                                    <p className="line-clamp-3 text-sm text-muted-foreground">
                                        {dataset.description}
                                    </p>
                                ) : null}
                                <p className="text-xs text-muted-foreground">
                                    {t('dataset.updated', {
                                        time: formatDateTime(dataset.updated_at, tag)
                                    })}
                                </p>
                            </div>
                            <div className="mt-auto flex flex-wrap gap-2 border-t border-border pt-4">
                                <Button variant="outline" onClick={() => setEditing(dataset.id)}>
                                    <PencilIcon />
                                    {t('common.edit')}
                                </Button>
                                <Button
                                    variant="outline"
                                    disabled={validateMutation.isPending}
                                    onClick={() => validateMutation.mutate(dataset)}
                                >
                                    <ListChecksIcon />
                                    {t('dataset.validate')}
                                </Button>
                                <Button variant="outline" asChild>
                                    <a href={datasetsApi.exportUrl(dataset.id)} download>
                                        <DownloadIcon />
                                        {t('dataset.export')}
                                    </a>
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    aria-label={`${t('common.delete')}: ${dataset.name}`}
                                    title={t('common.delete')}
                                    onClick={() => setDeleteTarget(dataset)}
                                >
                                    <Trash2Icon />
                                </Button>
                            </div>
                        </Card>
                    ))}
                </div>
            )}

            {editing !== undefined ? (
                <DatasetEditor
                    datasetId={editing}
                    onClose={() => setEditing(undefined)}
                    onSaved={(config) => {
                        setSaved(config)
                        setEditing(undefined)
                    }}
                />
            ) : null}

            <ValidationDialog
                report={report?.report ?? null}
                name={report?.name ?? ''}
                onClose={() => setReport(null)}
            />

            <AlertDialog
                open={deleteTarget !== null}
                onOpenChange={(open) => !open && setDeleteTarget(null)}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>{t('dataset.delete.title')}</AlertDialogTitle>
                        <AlertDialogDescription>
                            {t('dataset.delete.body', { name: deleteTarget?.name ?? '' })}
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                        <AlertDialogAction
                            variant="destructive"
                            disabled={deleteMutation.isPending}
                            onClick={(event) => {
                                event.preventDefault()
                                if (deleteTarget) deleteMutation.mutate(deleteTarget)
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

export default DatasetConfigs
