import { datasetsApi, mutationKeys, queryKeys } from '@/api/api'
import { getApiErrorMessage } from '@/api/client'
import type { ImageFile } from '@/api/types'
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Textarea } from '@/components/ui/textarea'
import { useI18n } from '@/i18n'
import { formatBytes, formatPercent } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import {
    ArrowLeftIcon,
    FolderIcon,
    ImagePlusIcon,
    PlusIcon,
    SaveIcon,
    SquareIcon,
    Trash2Icon,
    UploadIcon
} from 'lucide-react'
import { type DragEvent, useId, useRef, useState } from 'react'

const FOLDER_NAME = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/
const IMAGE_EXTENSION = /\.(png|jpe?g|webp|bmp)$/i
const PAGE_SIZE = 48

const stemOf = (name: string) => name.replace(/\.[^.]+$/, '')

type PendingUpload = { file: File; caption: string | null }

type Prepared = {
    uploads: PendingUpload[]
    orphanCaptions: number
    ignored: number
    totalBytes: number
}

/** Pairs images with their `.txt` sidecars by file stem and reads the captions in the browser. */
const prepareUploads = async (files: File[]): Promise<Prepared> => {
    const captions = new Map<string, File>()
    const images: File[] = []
    let ignored = 0

    for (const file of files) {
        if (/\.txt$/i.test(file.name)) captions.set(stemOf(file.name).toLowerCase(), file)
        else if (IMAGE_EXTENSION.test(file.name)) images.push(file)
        else ignored += 1
    }

    const used = new Set<string>()
    const uploads: PendingUpload[] = []
    for (const image of images) {
        const key = stemOf(image.name).toLowerCase()
        const sidecar = captions.get(key)
        let caption: string | null = null
        if (sidecar) {
            caption = (await sidecar.text()).replace(/^﻿/, '')
            used.add(key)
        }
        uploads.push({ file: image, caption })
    }

    return {
        uploads,
        orphanCaptions: captions.size - used.size,
        ignored,
        totalBytes: uploads.reduce((sum, upload) => sum + upload.file.size, 0)
    }
}

type UploadProgress = { index: number; total: number; name: string; percent: number }
type UploadResult = {
    completed: number
    total: number
    cancelled: boolean
    failed: Array<{ name: string; message: string }>
}

// ---- one thumbnail with its caption editor ----------------------------------------------------

type FileTileProps = {
    folder: string
    file: ImageFile
    onDelete: (file: ImageFile) => void
}

const FileTile = ({ folder, file, onDelete }: FileTileProps) => {
    const { t, tag } = useI18n()
    const queryClient = useQueryClient()
    const captionId = useId()
    // null means "not edited": show whatever the server has.
    const [draft, setDraft] = useState<string | null>(null)
    const saved = file.caption ?? ''
    const value = draft ?? saved
    const dirty = draft !== null && draft !== saved

    const saveMutation = useMutation({
        mutationFn: () => datasetsApi.saveCaption(folder, stemOf(file.name), value),
        onSuccess: async () => {
            setDraft(null)
            await queryClient.invalidateQueries({ queryKey: queryKeys.folderFiles(folder) })
        }
    })

    return (
        <Card compact className="flex flex-col gap-3 p-4">
            <img
                src={datasetsApi.fileUrl(folder, file.name)}
                alt={file.name}
                loading="lazy"
                decoding="async"
                className="aspect-square w-full rounded-lg border border-border bg-muted object-cover"
            />
            <div className="flex items-center justify-between gap-2 text-xs">
                <span className="min-w-0 truncate font-mono" title={file.name} translate="no">
                    {file.name}
                </span>
                <span className="tabular shrink-0 text-muted-foreground">
                    {formatBytes(file.size_bytes, tag)}
                </span>
            </div>
            <div className="flex flex-col gap-1.5">
                <Label htmlFor={captionId} className="text-xs font-semibold">
                    {t('folders.caption')}
                    {file.caption === null ? (
                        <Badge variant="muted">{t('folders.noCaption')}</Badge>
                    ) : null}
                </Label>
                <Textarea
                    id={captionId}
                    rows={3}
                    value={value}
                    className="min-h-20 text-sm"
                    onChange={(event) => setDraft(event.target.value)}
                />
            </div>
            {saveMutation.error ? (
                <p role="alert" className="text-xs text-destructive">
                    {getApiErrorMessage(saveMutation.error, t('folders.captionError'))}
                </p>
            ) : null}
            <div className="flex gap-2">
                <Button
                    variant="outline"
                    disabled={!dirty || saveMutation.isPending}
                    onClick={() => saveMutation.mutate()}
                >
                    <SaveIcon />
                    {saveMutation.isPending ? t('common.saving') : t('common.save')}
                </Button>
                <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`${t('common.delete')}: ${file.name}`}
                    title={t('common.delete')}
                    onClick={() => onDelete(file)}
                >
                    <Trash2Icon />
                </Button>
            </div>
        </Card>
    )
}

// ---- folder detail ----------------------------------------------------------------------------

type FolderDetailProps = {
    folder: string
    onBack: () => void
    onDeleted: () => void
}

const FolderDetail = ({ folder, onBack, onDeleted }: FolderDetailProps) => {
    const { t } = useI18n()
    const queryClient = useQueryClient()
    const inputRef = useRef<HTMLInputElement>(null)
    const abortRef = useRef<AbortController | null>(null)
    const [prepared, setPrepared] = useState<Prepared | null>(null)
    const [dragging, setDragging] = useState(false)
    const [progress, setProgress] = useState<UploadProgress | null>(null)
    const [result, setResult] = useState<UploadResult | null>(null)
    const [visible, setVisible] = useState(PAGE_SIZE)
    const [deleteFile, setDeleteFile] = useState<ImageFile | null>(null)
    const [deleteFolderOpen, setDeleteFolderOpen] = useState(false)
    const failedFallback = t('folders.uploadFailed')

    const filesQuery = useQuery({
        queryKey: queryKeys.folderFiles(folder),
        queryFn: () => datasetsApi.folderFiles(folder)
    })
    const files = filesQuery.data ?? []

    // Sequential, one request per file, so each stays small for HTTP proxies (docs/api.md, section 4).
    const uploadMutation = useMutation({
        mutationKey: mutationKeys.managedUpload,
        mutationFn: async (uploads: PendingUpload[]): Promise<UploadResult> => {
            const controller = new AbortController()
            abortRef.current = controller
            const totalBytes = uploads.reduce((sum, upload) => sum + upload.file.size, 0) || 1
            const failed: UploadResult['failed'] = []
            let doneBytes = 0
            let completed = 0

            for (const [index, upload] of uploads.entries()) {
                if (controller.signal.aborted) break
                const report = (loaded: number) =>
                    setProgress({
                        index,
                        total: uploads.length,
                        name: upload.file.name,
                        percent:
                            ((doneBytes + Math.min(loaded, upload.file.size)) / totalBytes) * 100
                    })
                report(0)
                try {
                    await datasetsApi.uploadFile(folder, upload.file, upload.caption, {
                        signal: controller.signal,
                        onProgress: (loaded) => report(loaded)
                    })
                    completed += 1
                } catch (error) {
                    if (axios.isCancel(error) || controller.signal.aborted) break
                    failed.push({
                        name: upload.file.name,
                        message: getApiErrorMessage(error, failedFallback)
                    })
                }
                doneBytes += upload.file.size
            }

            return {
                completed,
                total: uploads.length,
                cancelled: controller.signal.aborted,
                failed
            }
        },
        onSuccess: (outcome) => {
            setResult(outcome)
            setPrepared(null)
        },
        onSettled: async () => {
            abortRef.current = null
            setProgress(null)
            await Promise.all([
                queryClient.invalidateQueries({ queryKey: queryKeys.folderFiles(folder) }),
                queryClient.invalidateQueries({ queryKey: queryKeys.folders })
            ])
        }
    })
    const uploading = uploadMutation.isPending

    const deleteFileMutation = useMutation({
        mutationFn: (file: ImageFile) => datasetsApi.deleteFile(folder, file.name),
        onSuccess: async () => {
            setDeleteFile(null)
            await Promise.all([
                queryClient.invalidateQueries({ queryKey: queryKeys.folderFiles(folder) }),
                queryClient.invalidateQueries({ queryKey: queryKeys.folders })
            ])
        },
        onError: () => setDeleteFile(null)
    })
    const deleteFolderMutation = useMutation({
        mutationFn: () => datasetsApi.deleteFolder(folder),
        onSuccess: async () => {
            setDeleteFolderOpen(false)
            await queryClient.invalidateQueries({ queryKey: queryKeys.folders })
            onDeleted()
        },
        onError: () => setDeleteFolderOpen(false)
    })

    const choose = async (list: FileList | File[] | null) => {
        if (!list || list.length === 0) return
        setResult(null)
        setPrepared(await prepareUploads(Array.from(list)))
    }

    const onDrop = (event: DragEvent<HTMLDivElement>) => {
        event.preventDefault()
        setDragging(false)
        if (!uploading) void choose(event.dataTransfer.files)
    }

    const error = filesQuery.error ?? deleteFileMutation.error ?? deleteFolderMutation.error

    return (
        <div className="flex flex-col gap-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                    <Button
                        variant="outline"
                        size="icon"
                        disabled={uploading}
                        aria-label={t('common.back')}
                        onClick={onBack}
                    >
                        <ArrowLeftIcon />
                    </Button>
                    <div className="min-w-0">
                        <h2 className="truncate text-xl leading-[1.4] font-bold" translate="no">
                            {folder}
                        </h2>
                        <p className="tabular text-sm text-muted-foreground">
                            {t('folders.imageCount', { count: files.length })}
                        </p>
                    </div>
                </div>
                <Button
                    variant="destructive"
                    disabled={uploading}
                    onClick={() => setDeleteFolderOpen(true)}
                >
                    <Trash2Icon />
                    {t('folders.delete')}
                </Button>
            </div>

            {error ? (
                <Alert variant="destructive">
                    <AlertDescription className="mt-0">
                        {getApiErrorMessage(error, t('folders.requestError'))}
                    </AlertDescription>
                </Alert>
            ) : null}

            <Card
                onDragOver={(event) => {
                    event.preventDefault()
                    if (!uploading) setDragging(true)
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                className={cn(
                    'flex flex-col gap-4 transition-colors',
                    dragging && 'border-input bg-muted'
                )}
            >
                <div className="flex flex-col gap-1">
                    <h3 className="text-lg font-bold">{t('folders.upload.title')}</h3>
                    <p className="text-sm text-muted-foreground">{t('folders.upload.desc')}</p>
                </div>
                <input
                    ref={inputRef}
                    type="file"
                    multiple
                    accept=".png,.jpg,.jpeg,.webp,.bmp,.txt,image/png,image/jpeg,image/webp,image/bmp,text/plain"
                    className="hidden"
                    onChange={(event) => {
                        void choose(event.target.files)
                        event.target.value = ''
                    }}
                />
                <div className="flex flex-wrap items-center gap-3">
                    <Button
                        variant="outline"
                        disabled={uploading}
                        onClick={() => inputRef.current?.click()}
                    >
                        <ImagePlusIcon />
                        {t('folders.choose')}
                    </Button>
                    {prepared && prepared.uploads.length > 0 && !uploading ? (
                        <Button
                            variant="default"
                            onClick={() => uploadMutation.mutate(prepared.uploads)}
                        >
                            <UploadIcon />
                            {t('folders.startUpload', { count: prepared.uploads.length })}
                        </Button>
                    ) : null}
                    {uploading ? (
                        <Button variant="destructive" onClick={() => abortRef.current?.abort()}>
                            <SquareIcon />
                            {t('folders.cancelUpload')}
                        </Button>
                    ) : null}
                </div>

                {prepared ? (
                    <p className="text-sm" role="status">
                        {t('folders.selected', {
                            images: prepared.uploads.length,
                            captions: prepared.uploads.filter((upload) => upload.caption !== null)
                                .length,
                            size: formatBytes(prepared.totalBytes)
                        })}
                        {prepared.orphanCaptions > 0
                            ? ` ${t('folders.orphans', { count: prepared.orphanCaptions })}`
                            : ''}
                        {prepared.ignored > 0
                            ? ` ${t('folders.ignored', { count: prepared.ignored })}`
                            : ''}
                    </p>
                ) : null}

                {progress ? (
                    <div className="flex flex-col gap-2" aria-live="polite">
                        <div className="flex items-center justify-between gap-3 text-sm">
                            <span className="font-medium">
                                {t('folders.uploading', {
                                    index: Math.min(progress.index + 1, progress.total),
                                    total: progress.total
                                })}
                            </span>
                            <span className="tabular text-muted-foreground">
                                {formatPercent(progress.percent, undefined, 0)}
                            </span>
                        </div>
                        <Progress value={progress.percent} aria-label={t('folders.upload.title')} />
                        <p
                            className="truncate font-mono text-xs text-muted-foreground"
                            translate="no"
                        >
                            {progress.name}
                        </p>
                    </div>
                ) : null}

                {result ? (
                    <Alert variant={result.failed.length > 0 ? 'destructive' : 'note'}>
                        <AlertTitle>
                            {result.cancelled
                                ? t('folders.result.cancelled', {
                                      completed: result.completed,
                                      total: result.total
                                  })
                                : t('folders.result.done', {
                                      completed: result.completed,
                                      total: result.total
                                  })}
                        </AlertTitle>
                        {result.failed.length > 0 ? (
                            <AlertDescription>
                                <ul className="list-disc pl-5">
                                    {result.failed.map((failure) => (
                                        <li key={failure.name}>
                                            <span className="font-mono" translate="no">
                                                {failure.name}
                                            </span>
                                            : {failure.message}
                                        </li>
                                    ))}
                                </ul>
                            </AlertDescription>
                        ) : null}
                    </Alert>
                ) : null}
            </Card>

            {!filesQuery.isPending && files.length === 0 ? (
                <p className="rounded-xl border border-dashed border-border px-6 py-16 text-center text-sm text-muted-foreground">
                    {t('folders.emptyFolder')}
                </p>
            ) : (
                <>
                    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                        {files.slice(0, visible).map((file) => (
                            <FileTile
                                key={file.name}
                                folder={folder}
                                file={file}
                                onDelete={setDeleteFile}
                            />
                        ))}
                    </div>
                    {visible < files.length ? (
                        <div className="flex justify-center">
                            <Button
                                variant="outline"
                                onClick={() => setVisible((count) => count + PAGE_SIZE)}
                            >
                                {t('folders.showMore', { count: files.length - visible })}
                            </Button>
                        </div>
                    ) : null}
                </>
            )}

            <AlertDialog
                open={deleteFile !== null}
                onOpenChange={(open) => !open && setDeleteFile(null)}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>{t('folders.deleteFile.title')}</AlertDialogTitle>
                        <AlertDialogDescription>
                            {t('folders.deleteFile.body', { name: deleteFile?.name ?? '' })}
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                        <AlertDialogAction
                            variant="destructive"
                            disabled={deleteFileMutation.isPending}
                            onClick={(event) => {
                                event.preventDefault()
                                if (deleteFile) deleteFileMutation.mutate(deleteFile)
                            }}
                        >
                            {t('common.delete')}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog open={deleteFolderOpen} onOpenChange={setDeleteFolderOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>{t('folders.delete.title')}</AlertDialogTitle>
                        <AlertDialogDescription>
                            {t('folders.delete.body', { name: folder })}
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                        <AlertDialogAction
                            variant="destructive"
                            disabled={deleteFolderMutation.isPending}
                            onClick={(event) => {
                                event.preventDefault()
                                deleteFolderMutation.mutate()
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

// ---- folder list ------------------------------------------------------------------------------

const ImageFolders = () => {
    const { t, tag } = useI18n()
    const queryClient = useQueryClient()
    const nameId = useId()
    const [selected, setSelected] = useState<string | null>(null)
    const [name, setName] = useState('')

    const foldersQuery = useQuery({ queryKey: queryKeys.folders, queryFn: datasetsApi.folders })
    const folders = foldersQuery.data ?? []
    const trimmed = name.trim()
    const nameInvalid = trimmed !== '' && !FOLDER_NAME.test(trimmed)

    const createMutation = useMutation({
        mutationFn: (folderName: string) => datasetsApi.createFolder(folderName),
        onSuccess: async (folder) => {
            setName('')
            await queryClient.invalidateQueries({ queryKey: queryKeys.folders })
            setSelected(folder.name)
        }
    })

    if (selected) {
        return (
            <FolderDetail
                key={selected}
                folder={selected}
                onBack={() => setSelected(null)}
                onDeleted={() => setSelected(null)}
            />
        )
    }

    return (
        <div className="flex flex-col gap-6">
            <Card className="flex flex-col gap-3">
                <div>
                    <h2 className="text-lg font-bold">{t('folders.create.title')}</h2>
                    <p className="text-sm text-muted-foreground">{t('folders.create.desc')}</p>
                </div>
                <form
                    className="flex flex-col gap-2 sm:flex-row sm:items-end"
                    onSubmit={(event) => {
                        event.preventDefault()
                        if (trimmed && !nameInvalid) createMutation.mutate(trimmed)
                    }}
                >
                    <div className="flex flex-1 flex-col gap-2">
                        <Label htmlFor={nameId} className="text-sm font-semibold">
                            {t('folders.name')}
                        </Label>
                        <Input
                            id={nameId}
                            value={name}
                            maxLength={64}
                            autoComplete="off"
                            spellCheck={false}
                            aria-invalid={nameInvalid || undefined}
                            className="font-mono"
                            onChange={(event) => setName(event.target.value)}
                        />
                    </div>
                    <Button
                        type="submit"
                        variant="default"
                        disabled={!trimmed || nameInvalid || createMutation.isPending}
                    >
                        <PlusIcon />
                        {t('folders.create')}
                    </Button>
                </form>
                <p
                    className={cn(
                        'text-[0.8125rem]',
                        nameInvalid ? 'text-destructive' : 'text-muted-foreground'
                    )}
                >
                    {t('folders.nameRule')}
                </p>
                {createMutation.error ? (
                    <p role="alert" className="text-sm text-destructive">
                        {getApiErrorMessage(createMutation.error, t('folders.createError'))}
                    </p>
                ) : null}
            </Card>

            {foldersQuery.error ? (
                <Alert variant="destructive">
                    <AlertDescription className="mt-0">
                        {getApiErrorMessage(foldersQuery.error, t('folders.requestError'))}
                    </AlertDescription>
                </Alert>
            ) : null}

            {!foldersQuery.isPending && folders.length === 0 ? (
                <p className="rounded-xl border border-dashed border-border px-6 py-16 text-center text-sm text-muted-foreground">
                    {t('folders.empty')}
                </p>
            ) : (
                <ul className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
                    {folders.map((folder) => (
                        <li key={folder.name}>
                            <button
                                type="button"
                                className="flex w-full items-start gap-4 rounded-xl border border-border bg-card p-5 text-left transition-colors hover:border-input motion-reduce:transition-none"
                                onClick={() => setSelected(folder.name)}
                            >
                                <FolderIcon aria-hidden className="mt-0.5 size-5 shrink-0" />
                                <span className="flex min-w-0 flex-1 flex-col gap-1">
                                    <span className="truncate font-semibold" translate="no">
                                        {folder.name}
                                    </span>
                                    <span className="tabular text-sm text-muted-foreground">
                                        {t('folders.counts', {
                                            images: folder.images,
                                            captions: folder.captions
                                        })}
                                    </span>
                                    <span className="tabular text-xs text-muted-foreground">
                                        {formatBytes(folder.size_bytes, tag)}
                                    </span>
                                    <code
                                        className="truncate font-mono text-xs text-muted-foreground"
                                        translate="no"
                                    >
                                        {folder.path}
                                    </code>
                                </span>
                            </button>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    )
}

export default ImageFolders
