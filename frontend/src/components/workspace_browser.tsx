import { fsApi, queryKeys } from '@/api/api'
import { getApiErrorMessage, httpStatus } from '@/api/client'
import { Button } from '@/components/ui/button'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle
} from '@/components/ui/dialog'
import { Switch } from '@/components/ui/switch'
import { useI18n } from '@/i18n'
import { formatBytes } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useQuery } from '@tanstack/react-query'
import { ChevronRightIcon, CornerLeftUpIcon, FileIcon, FolderIcon } from 'lucide-react'
import { useEffect, useId, useState } from 'react'

export type PathMode = 'file' | 'folder' | 'any'

type WorkspaceBrowserProps = {
    mode: PathMode
    // Comma separated extension filter, such as ".safetensors,.ckpt". Applies to files only.
    extensions?: string
    // The current field value. Its folder is where the browser opens, when it is inside the workspace.
    initialValue: string
    onSelect: (path: string) => void
    onClose: () => void
}

const joinPath = (dir: string, name: string) => (dir ? `${dir}/${name}` : name)

const startingFolder = (value: string) => {
    const normalized = value.trim().replace(/\\/g, '/')
    // Absolute paths and parent traversal cannot be listed (docs/api.md, section 3).
    if (!normalized || /^([a-zA-Z]:|\/)/.test(normalized) || normalized.includes('..')) return ''
    const index = normalized.lastIndexOf('/')
    return index > 0 ? normalized.slice(0, index) : ''
}

const WorkspaceBrowser = ({
    mode,
    extensions,
    initialValue,
    onSelect,
    onClose
}: WorkspaceBrowserProps) => {
    const { t, tag } = useI18n()
    const allFilesId = useId()
    const [path, setPath] = useState(() => startingFolder(initialValue))
    const [showAll, setShowAll] = useState(false)
    const filter = mode === 'folder' || showAll ? '' : (extensions ?? '')

    const listing = useQuery({
        queryKey: queryKeys.fs(path, filter),
        queryFn: () => fsApi.list(path, filter || undefined),
        retry: false,
        staleTime: 0
    })

    // A remembered folder can disappear; fall back to the workspace root.
    useEffect(() => {
        const status = httpStatus(listing.error)
        if (path && (status === 404 || status === 400)) setPath('')
    }, [listing.error, path])

    const segments = path ? path.split('/') : []
    const entries = (listing.data?.entries ?? []).filter(
        (entry) => mode !== 'folder' || entry.kind === 'dir'
    )
    const canChooseFolder = mode === 'folder' || mode === 'any'

    return (
        <Dialog open onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-2xl">
                <DialogHeader>
                    <DialogTitle>{t('browser.title')}</DialogTitle>
                    <DialogDescription>
                        {mode === 'folder'
                            ? t('browser.hintFolder')
                            : mode === 'any'
                              ? t('browser.hintAny')
                              : t('browser.hintFile')}
                    </DialogDescription>
                </DialogHeader>

                <nav
                    aria-label={t('browser.location')}
                    className="flex flex-wrap items-center gap-1 text-sm"
                >
                    <Button variant="ghost" onClick={() => setPath('')} className="px-3">
                        {t('browser.root')}
                    </Button>
                    {segments.map((segment, index) => (
                        <span key={`${index}:${segment}`} className="flex items-center gap-1">
                            <ChevronRightIcon className="size-4 text-muted-foreground" />
                            <Button
                                variant="ghost"
                                className="px-3"
                                onClick={() => setPath(segments.slice(0, index + 1).join('/'))}
                            >
                                {segment}
                            </Button>
                        </span>
                    ))}
                </nav>

                <div
                    className="max-h-[22rem] min-h-40 overflow-y-auto rounded-lg border border-border bg-card"
                    aria-busy={listing.isFetching}
                >
                    {listing.isError ? (
                        <p role="alert" className="p-4 text-sm text-destructive">
                            {getApiErrorMessage(listing.error, t('browser.error'))}
                        </p>
                    ) : listing.isPending ? (
                        <p className="p-4 text-sm text-muted-foreground">{t('common.loading')}</p>
                    ) : (
                        <ul className="divide-y divide-border">
                            {path ? (
                                <li>
                                    <button
                                        type="button"
                                        className="flex min-h-10 w-full items-center gap-3 px-4 py-2 text-left text-sm hover:bg-muted"
                                        onClick={() => setPath(segments.slice(0, -1).join('/'))}
                                    >
                                        <CornerLeftUpIcon className="size-4 shrink-0 text-muted-foreground" />
                                        {t('browser.up')}
                                    </button>
                                </li>
                            ) : null}
                            {entries.map((entry) => (
                                <li key={entry.name}>
                                    <button
                                        type="button"
                                        className={cn(
                                            'flex min-h-10 w-full items-center gap-3 px-4 py-2 text-left text-sm hover:bg-muted',
                                            entry.kind === 'file' &&
                                                mode === 'folder' &&
                                                'opacity-50'
                                        )}
                                        onClick={() =>
                                            entry.kind === 'dir'
                                                ? setPath(joinPath(path, entry.name))
                                                : onSelect(joinPath(path, entry.name))
                                        }
                                    >
                                        {entry.kind === 'dir' ? (
                                            <FolderIcon className="size-4 shrink-0" />
                                        ) : (
                                            <FileIcon className="size-4 shrink-0 text-muted-foreground" />
                                        )}
                                        <span className="min-w-0 flex-1 truncate" translate="no">
                                            {entry.name}
                                        </span>
                                        {entry.size_bytes !== null ? (
                                            <span className="tabular shrink-0 text-xs text-muted-foreground">
                                                {formatBytes(entry.size_bytes, tag)}
                                            </span>
                                        ) : null}
                                    </button>
                                </li>
                            ))}
                            {entries.length === 0 ? (
                                <li className="p-6 text-center text-sm text-muted-foreground">
                                    {t('browser.empty')}
                                </li>
                            ) : null}
                        </ul>
                    )}
                </div>

                {mode !== 'folder' && extensions ? (
                    <label
                        htmlFor={allFilesId}
                        className="flex min-h-10 cursor-pointer items-center gap-3 text-sm"
                    >
                        <Switch id={allFilesId} checked={showAll} onCheckedChange={setShowAll} />
                        {t('browser.allFiles')}
                        <span className="text-xs text-muted-foreground" translate="no">
                            ({extensions.split(',').join(' ')})
                        </span>
                    </label>
                ) : null}

                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>
                        {t('common.cancel')}
                    </Button>
                    {canChooseFolder ? (
                        <Button variant="default" onClick={() => onSelect(path || '.')}>
                            {t('browser.useFolder')}
                        </Button>
                    ) : null}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

export default WorkspaceBrowser
