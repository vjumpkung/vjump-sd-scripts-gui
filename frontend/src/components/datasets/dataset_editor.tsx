import {
    type DatasetDraft,
    type DraftIssue,
    type EditorDraft,
    type GeneralDraft,
    type SubsetDraft,
    type TriState,
    configToDraft,
    draftToConfig,
    emptyDataset,
    emptyDraft,
    emptySubset
} from './dataset_model'
import { datasetsApi, queryKeys } from '@/api/api'
import { getApiErrorMessage } from '@/api/client'
import type { DatasetConfig, DatasetKind } from '@/api/types'
import PathInput from '@/components/path_input'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { type I18nKey, useI18n } from '@/i18n'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { PlusIcon, Trash2Icon } from 'lucide-react'
import { type ReactNode, useEffect, useId, useRef, useState } from 'react'

// ---- small field helpers ---------------------------------------------------------------------

type TextFieldProps = {
    label: string
    value: string
    onChange: (value: string) => void
    hint?: string
    placeholder?: string
    mono?: boolean
    inputMode?: 'numeric' | 'decimal'
    required?: boolean
}

const TextField = ({
    label,
    value,
    onChange,
    hint,
    placeholder,
    mono,
    inputMode,
    required
}: TextFieldProps) => {
    const id = useId()
    return (
        <div className="flex min-w-0 flex-col gap-2">
            <Label htmlFor={id} className="text-sm font-semibold">
                {label}
                {required ? (
                    <span aria-hidden className="text-pink-ink">
                        *
                    </span>
                ) : null}
            </Label>
            <Input
                id={id}
                value={value}
                inputMode={inputMode}
                placeholder={placeholder}
                spellCheck={false}
                autoComplete="off"
                className={mono ? 'font-mono' : undefined}
                onChange={(event) => onChange(event.target.value)}
            />
            {hint ? (
                <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">{hint}</p>
            ) : null}
        </div>
    )
}

const INHERIT = '__inherit__'

type TriFieldProps = {
    label: string
    value: TriState
    onChange: (value: TriState) => void
    hint?: string
}

const TriField = ({ label, value, onChange, hint }: TriFieldProps) => {
    const { t } = useI18n()
    const id = useId()
    return (
        <div className="flex min-w-0 flex-col gap-2">
            <Label htmlFor={id} className="text-sm font-semibold">
                {label}
            </Label>
            <Select
                value={value === '' ? INHERIT : value}
                onValueChange={(next) => onChange(next === INHERIT ? '' : (next as TriState))}
            >
                <SelectTrigger id={id}>
                    <SelectValue />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value={INHERIT}>{t('dataset.tri.unset')}</SelectItem>
                    <SelectItem value="true">{t('common.yes')}</SelectItem>
                    <SelectItem value="false">{t('common.no')}</SelectItem>
                </SelectContent>
            </Select>
            {hint ? (
                <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">{hint}</p>
            ) : null}
        </div>
    )
}

type AdditionalFieldProps = {
    value: string
    onChange: (value: string) => void
}

const AdditionalField = ({ value, onChange }: AdditionalFieldProps) => {
    const { t } = useI18n()
    const id = useId()
    return (
        <div className="flex flex-col gap-2 md:col-span-2">
            <Label htmlFor={id} className="text-sm font-semibold">
                {t('dataset.additional')}
            </Label>
            <Textarea
                id={id}
                rows={3}
                value={value}
                spellCheck={false}
                translate="no"
                placeholder={'keep_tokens_separator = "|||"\ncaption_prefix = "masterpiece, "'}
                className="font-mono"
                onChange={(event) => onChange(event.target.value)}
            />
            <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">
                {t('dataset.additional.help')}
            </p>
        </div>
    )
}

type FolderFieldProps = {
    label: string
    value: string
    onChange: (value: string) => void
    mode: 'folder' | 'file'
    extensions?: string
    required?: boolean
    hint?: string
    // Offer the image folders under datasets/ as a quick pick.
    folders?: boolean
}

const FolderField = ({
    label,
    value,
    onChange,
    mode,
    extensions,
    required,
    hint,
    folders
}: FolderFieldProps) => {
    const { t } = useI18n()
    const id = useId()
    const foldersQuery = useQuery({
        queryKey: queryKeys.folders,
        queryFn: datasetsApi.folders,
        enabled: Boolean(folders)
    })
    const list = foldersQuery.data ?? []

    return (
        <div className="flex min-w-0 flex-col gap-2 md:col-span-2">
            <Label htmlFor={id} className="text-sm font-semibold">
                {label}
                {required ? (
                    <span aria-hidden className="text-pink-ink">
                        *
                    </span>
                ) : null}
            </Label>
            <PathInput
                id={id}
                value={value}
                onChange={onChange}
                mode={mode}
                extensions={extensions}
            />
            {folders && list.length > 0 ? (
                <Select value="" onValueChange={onChange}>
                    <SelectTrigger aria-label={t('dataset.pickFolder')}>
                        <SelectValue placeholder={t('dataset.pickFolder')} />
                    </SelectTrigger>
                    <SelectContent className="max-h-72">
                        {list.map((folder) => (
                            <SelectItem key={folder.name} value={folder.path}>
                                <span translate="no">{folder.name}</span>
                                <span className="text-muted-foreground">
                                    {' · '}
                                    {t('folders.imageCount', { count: folder.images })}
                                </span>
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            ) : null}
            {hint ? (
                <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">{hint}</p>
            ) : null}
        </div>
    )
}

const Block = ({
    title,
    actions,
    children,
    nested
}: {
    title: string
    actions?: ReactNode
    children: ReactNode
    nested?: boolean
}) => (
    <section
        className={
            nested
                ? 'flex flex-col gap-5 rounded-lg border border-border bg-background p-4'
                : 'flex flex-col gap-5 rounded-xl border border-border p-5'
        }
    >
        <div className="flex items-center justify-between gap-3">
            <h3 className={nested ? 'text-base font-semibold' : 'text-lg font-bold'}>{title}</h3>
            {actions}
        </div>
        {children}
    </section>
)

// ---- the form --------------------------------------------------------------------------------

const SUBSET_KINDS: DatasetKind[] = ['dreambooth', 'finetune', 'controlnet']

type EditorFormProps = {
    datasetId: string | null
    initial: EditorDraft
    warnings: string[]
    onClose: () => void
    onSaved: (config: DatasetConfig) => void
}

const EditorForm = ({ datasetId, initial, warnings, onClose, onSaved }: EditorFormProps) => {
    const { t } = useI18n()
    const queryClient = useQueryClient()
    const [draft, setDraft] = useState(initial)
    const [issues, setIssues] = useState<DraftIssue[]>([])
    const nameId = useId()
    const descriptionId = useId()
    const feedbackRef = useRef<HTMLDivElement>(null)

    const saveMutation = useMutation({
        mutationFn: (body: Parameters<typeof datasetsApi.create>[0]) =>
            datasetId ? datasetsApi.update(datasetId, body) : datasetsApi.create(body),
        onSuccess: async (config) => {
            await queryClient.invalidateQueries({ queryKey: queryKeys.datasets })
            onSaved(config)
        }
    })

    // The dialog body scrolls, so bring problems into view instead of leaving them below the fold.
    useEffect(() => {
        if (issues.length > 0 || saveMutation.error) {
            feedbackRef.current?.scrollIntoView({ block: 'nearest' })
        }
    }, [issues, saveMutation.error])

    const patchGeneral = (patch: Partial<GeneralDraft>) =>
        setDraft((current) => ({ ...current, general: { ...current.general, ...patch } }))
    const patchDataset = (index: number, patch: Partial<DatasetDraft>) =>
        setDraft((current) => ({
            ...current,
            datasets: current.datasets.map((item, at) =>
                at === index ? { ...item, ...patch } : item
            )
        }))
    const patchSubset = (datasetIndex: number, subsetIndex: number, patch: Partial<SubsetDraft>) =>
        setDraft((current) => ({
            ...current,
            datasets: current.datasets.map((dataset, at) =>
                at === datasetIndex
                    ? {
                          ...dataset,
                          subsets: dataset.subsets.map((subset, subsetAt) =>
                              subsetAt === subsetIndex ? { ...subset, ...patch } : subset
                          )
                      }
                    : dataset
            )
        }))

    const save = () => {
        const { config, issues: found } = draftToConfig(draft)
        const all: DraftIssue[] = draft.name.trim()
            ? found
            : [{ key: 'dataset.issue.name' }, ...found]
        setIssues(all)
        if (all.length > 0) return
        saveMutation.mutate({ name: draft.name.trim(), description: draft.description, config })
    }

    const g = draft.general

    return (
        <>
            <div className="flex flex-col gap-6">
                {warnings.length > 0 ? (
                    <Alert>
                        <AlertTitle>{t('dataset.warnings')}</AlertTitle>
                        <AlertDescription>
                            <ul className="list-disc pl-5">
                                {warnings.map((warning) => (
                                    <li key={warning}>{warning}</li>
                                ))}
                            </ul>
                        </AlertDescription>
                    </Alert>
                ) : null}

                <div className="grid gap-5 md:grid-cols-2">
                    <div className="flex flex-col gap-2">
                        <Label htmlFor={nameId} className="text-sm font-semibold">
                            {t('dataset.name')}
                            <span aria-hidden className="text-pink-ink">
                                *
                            </span>
                        </Label>
                        <Input
                            id={nameId}
                            value={draft.name}
                            maxLength={120}
                            autoComplete="off"
                            onChange={(event) =>
                                setDraft((current) => ({ ...current, name: event.target.value }))
                            }
                        />
                    </div>
                    <div className="flex flex-col gap-2">
                        <Label htmlFor={descriptionId} className="text-sm font-semibold">
                            {t('dataset.description')}
                        </Label>
                        <Input
                            id={descriptionId}
                            value={draft.description}
                            autoComplete="off"
                            onChange={(event) =>
                                setDraft((current) => ({
                                    ...current,
                                    description: event.target.value
                                }))
                            }
                        />
                    </div>
                </div>

                <Block title={t('dataset.general')}>
                    <p className="-mt-3 text-sm text-muted-foreground">
                        {t('dataset.general.help')}
                    </p>
                    <div className="grid gap-5 md:grid-cols-2">
                        <TriField
                            label={t('dataset.field.shuffleCaption')}
                            value={g.shuffle_caption}
                            onChange={(value) => patchGeneral({ shuffle_caption: value })}
                        />
                        <TextField
                            label={t('dataset.field.captionExtension')}
                            value={g.caption_extension}
                            placeholder=".txt"
                            mono
                            onChange={(value) => patchGeneral({ caption_extension: value })}
                        />
                        <TextField
                            label={t('dataset.field.keepTokens')}
                            value={g.keep_tokens}
                            inputMode="numeric"
                            onChange={(value) => patchGeneral({ keep_tokens: value })}
                        />
                        <TriField
                            label={t('dataset.field.flipAug')}
                            value={g.flip_aug}
                            onChange={(value) => patchGeneral({ flip_aug: value })}
                        />
                        <TriField
                            label={t('dataset.field.colorAug')}
                            value={g.color_aug}
                            onChange={(value) => patchGeneral({ color_aug: value })}
                        />
                        <TriField
                            label={t('dataset.field.randomCrop')}
                            value={g.random_crop}
                            onChange={(value) => patchGeneral({ random_crop: value })}
                        />
                        <TextField
                            label={t('dataset.field.captionDropout')}
                            value={g.caption_dropout_rate}
                            inputMode="decimal"
                            onChange={(value) => patchGeneral({ caption_dropout_rate: value })}
                        />
                        <AdditionalField
                            value={g.additional}
                            onChange={(value) => patchGeneral({ additional: value })}
                        />
                    </div>
                </Block>

                {draft.datasets.map((dataset, datasetIndex) => (
                    <Block
                        key={dataset.uid}
                        title={t('dataset.datasetN', { n: datasetIndex + 1 })}
                        actions={
                            <Button
                                variant="ghost"
                                disabled={draft.datasets.length === 1}
                                onClick={() =>
                                    setDraft((current) => ({
                                        ...current,
                                        datasets: current.datasets.filter(
                                            (_, at) => at !== datasetIndex
                                        )
                                    }))
                                }
                            >
                                <Trash2Icon />
                                {t('dataset.removeDataset')}
                            </Button>
                        }
                    >
                        <div className="grid gap-5 md:grid-cols-2">
                            <div className="flex min-w-0 flex-col gap-2">
                                <span className="text-sm font-semibold" id={`${dataset.uid}-res`}>
                                    {t('dataset.field.resolution')}
                                </span>
                                <div
                                    role="group"
                                    aria-labelledby={`${dataset.uid}-res`}
                                    className="flex items-center gap-2"
                                >
                                    <Input
                                        value={dataset.width}
                                        inputMode="numeric"
                                        aria-label={t('dataset.field.width')}
                                        onChange={(event) =>
                                            patchDataset(datasetIndex, {
                                                width: event.target.value
                                            })
                                        }
                                    />
                                    <span aria-hidden className="text-muted-foreground">
                                        ×
                                    </span>
                                    <Input
                                        value={dataset.height}
                                        inputMode="numeric"
                                        aria-label={t('dataset.field.height')}
                                        onChange={(event) =>
                                            patchDataset(datasetIndex, {
                                                height: event.target.value
                                            })
                                        }
                                    />
                                </div>
                            </div>
                            <TextField
                                label={t('dataset.field.batchSize')}
                                value={dataset.batch_size}
                                inputMode="numeric"
                                onChange={(value) =>
                                    patchDataset(datasetIndex, { batch_size: value })
                                }
                            />
                            <TriField
                                label={t('dataset.field.enableBucket')}
                                value={dataset.enable_bucket}
                                onChange={(value) =>
                                    patchDataset(datasetIndex, { enable_bucket: value })
                                }
                            />
                            <TriField
                                label={t('dataset.field.noUpscale')}
                                value={dataset.bucket_no_upscale}
                                onChange={(value) =>
                                    patchDataset(datasetIndex, { bucket_no_upscale: value })
                                }
                            />
                            <TextField
                                label={t('dataset.field.minBucket')}
                                value={dataset.min_bucket_reso}
                                inputMode="numeric"
                                placeholder="256"
                                onChange={(value) =>
                                    patchDataset(datasetIndex, { min_bucket_reso: value })
                                }
                            />
                            <TextField
                                label={t('dataset.field.maxBucket')}
                                value={dataset.max_bucket_reso}
                                inputMode="numeric"
                                placeholder="1024"
                                onChange={(value) =>
                                    patchDataset(datasetIndex, { max_bucket_reso: value })
                                }
                            />
                            <TextField
                                label={t('dataset.field.bucketSteps')}
                                value={dataset.bucket_reso_steps}
                                inputMode="numeric"
                                placeholder="64"
                                onChange={(value) =>
                                    patchDataset(datasetIndex, { bucket_reso_steps: value })
                                }
                            />
                            <AdditionalField
                                value={dataset.additional}
                                onChange={(value) =>
                                    patchDataset(datasetIndex, { additional: value })
                                }
                            />
                        </div>

                        {dataset.subsets.map((subset, subsetIndex) => (
                            <Block
                                nested
                                key={subset.uid}
                                title={t('dataset.subsetN', { n: subsetIndex + 1 })}
                                actions={
                                    <Button
                                        variant="ghost"
                                        disabled={dataset.subsets.length === 1}
                                        onClick={() =>
                                            patchDataset(datasetIndex, {
                                                subsets: dataset.subsets.filter(
                                                    (_, at) => at !== subsetIndex
                                                )
                                            })
                                        }
                                    >
                                        <Trash2Icon />
                                        {t('dataset.removeSubset')}
                                    </Button>
                                }
                            >
                                <div className="grid gap-5 md:grid-cols-2">
                                    <div className="flex min-w-0 flex-col gap-2 md:col-span-2">
                                        <Label className="text-sm font-semibold">
                                            {t('dataset.field.kind')}
                                        </Label>
                                        <Select
                                            value={subset.kind}
                                            onValueChange={(value) =>
                                                patchSubset(datasetIndex, subsetIndex, {
                                                    kind: value as DatasetKind
                                                })
                                            }
                                        >
                                            <SelectTrigger aria-label={t('dataset.field.kind')}>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {SUBSET_KINDS.map((kind) => (
                                                    <SelectItem key={kind} value={kind}>
                                                        {t(`dataset.kind.${kind}` as I18nKey)}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    {subset.kind !== 'finetune' ? (
                                        <FolderField
                                            folders
                                            required
                                            mode="folder"
                                            label={t('dataset.field.imageDir')}
                                            value={subset.image_dir}
                                            hint={t('dataset.field.imageDir.help')}
                                            onChange={(value) =>
                                                patchSubset(datasetIndex, subsetIndex, {
                                                    image_dir: value
                                                })
                                            }
                                        />
                                    ) : null}
                                    {subset.kind === 'finetune' ? (
                                        <>
                                            <FolderField
                                                required
                                                mode="file"
                                                extensions=".json"
                                                label={t('dataset.field.metadataFile')}
                                                value={subset.metadata_file}
                                                hint={t('dataset.field.metadataFile.help')}
                                                onChange={(value) =>
                                                    patchSubset(datasetIndex, subsetIndex, {
                                                        metadata_file: value
                                                    })
                                                }
                                            />
                                            <FolderField
                                                folders
                                                mode="folder"
                                                label={t('dataset.field.imageDirOptional')}
                                                value={subset.image_dir}
                                                onChange={(value) =>
                                                    patchSubset(datasetIndex, subsetIndex, {
                                                        image_dir: value
                                                    })
                                                }
                                            />
                                        </>
                                    ) : null}
                                    {subset.kind === 'controlnet' ? (
                                        <FolderField
                                            folders
                                            required
                                            mode="folder"
                                            label={t('dataset.field.conditioningDir')}
                                            value={subset.conditioning_data_dir}
                                            hint={t('dataset.field.conditioningDir.help')}
                                            onChange={(value) =>
                                                patchSubset(datasetIndex, subsetIndex, {
                                                    conditioning_data_dir: value
                                                })
                                            }
                                        />
                                    ) : null}

                                    <TextField
                                        label={t('dataset.field.numRepeats')}
                                        value={subset.num_repeats}
                                        inputMode="numeric"
                                        placeholder="1"
                                        hint={t('dataset.field.numRepeats.help')}
                                        onChange={(value) =>
                                            patchSubset(datasetIndex, subsetIndex, {
                                                num_repeats: value
                                            })
                                        }
                                    />
                                    {subset.kind === 'dreambooth' ? (
                                        <TextField
                                            label={t('dataset.field.classTokens')}
                                            value={subset.class_tokens}
                                            hint={t('dataset.field.classTokens.help')}
                                            onChange={(value) =>
                                                patchSubset(datasetIndex, subsetIndex, {
                                                    class_tokens: value
                                                })
                                            }
                                        />
                                    ) : null}
                                    {subset.kind !== 'finetune' ? (
                                        <TextField
                                            label={t('dataset.field.captionExtension')}
                                            value={subset.caption_extension}
                                            placeholder=".txt"
                                            mono
                                            onChange={(value) =>
                                                patchSubset(datasetIndex, subsetIndex, {
                                                    caption_extension: value
                                                })
                                            }
                                        />
                                    ) : null}
                                    {subset.kind === 'dreambooth' ? (
                                        <TriField
                                            label={t('dataset.field.isReg')}
                                            value={subset.is_reg}
                                            hint={t('dataset.field.isReg.help')}
                                            onChange={(value) =>
                                                patchSubset(datasetIndex, subsetIndex, {
                                                    is_reg: value
                                                })
                                            }
                                        />
                                    ) : null}
                                    <TextField
                                        label={t('dataset.field.keepTokens')}
                                        value={subset.keep_tokens}
                                        inputMode="numeric"
                                        onChange={(value) =>
                                            patchSubset(datasetIndex, subsetIndex, {
                                                keep_tokens: value
                                            })
                                        }
                                    />
                                    <TriField
                                        label={t('dataset.field.shuffleCaption')}
                                        value={subset.shuffle_caption}
                                        onChange={(value) =>
                                            patchSubset(datasetIndex, subsetIndex, {
                                                shuffle_caption: value
                                            })
                                        }
                                    />
                                    <TriField
                                        label={t('dataset.field.flipAug')}
                                        value={subset.flip_aug}
                                        onChange={(value) =>
                                            patchSubset(datasetIndex, subsetIndex, {
                                                flip_aug: value
                                            })
                                        }
                                    />
                                    <AdditionalField
                                        value={subset.additional}
                                        onChange={(value) =>
                                            patchSubset(datasetIndex, subsetIndex, {
                                                additional: value
                                            })
                                        }
                                    />
                                </div>
                            </Block>
                        ))}

                        <div>
                            <Button
                                variant="outline"
                                onClick={() =>
                                    patchDataset(datasetIndex, {
                                        subsets: [...dataset.subsets, emptySubset()]
                                    })
                                }
                            >
                                <PlusIcon />
                                {t('dataset.addSubset')}
                            </Button>
                        </div>
                    </Block>
                ))}

                <div>
                    <Button
                        variant="outline"
                        onClick={() =>
                            setDraft((current) => ({
                                ...current,
                                datasets: [...current.datasets, emptyDataset()]
                            }))
                        }
                    >
                        <PlusIcon />
                        {t('dataset.addDataset')}
                    </Button>
                </div>

                <div ref={feedbackRef} className="flex flex-col gap-6">
                    {issues.length > 0 ? (
                        <Alert variant="destructive">
                            <AlertTitle>{t('dataset.issues')}</AlertTitle>
                            <AlertDescription>
                                <ul className="list-disc pl-5">
                                    {issues.map((issue, index) => (
                                        <li key={index}>
                                            {t(issue.key, {
                                                ...issue.vars,
                                                ...(issue.vars?.field
                                                    ? { field: t(issue.vars.field as I18nKey) }
                                                    : {})
                                            })}
                                        </li>
                                    ))}
                                </ul>
                            </AlertDescription>
                        </Alert>
                    ) : null}
                    {saveMutation.error ? (
                        <Alert variant="destructive">
                            <AlertDescription className="mt-0">
                                {getApiErrorMessage(saveMutation.error, t('dataset.saveError'))}
                            </AlertDescription>
                        </Alert>
                    ) : null}
                </div>
            </div>

            <DialogFooter className="sticky -bottom-6 -mx-6 -mb-6 bg-popover px-6 py-4">
                <Button variant="outline" onClick={onClose}>
                    {t('common.cancel')}
                </Button>
                <Button variant="default" disabled={saveMutation.isPending} onClick={save}>
                    {saveMutation.isPending ? t('common.saving') : t('common.save')}
                </Button>
            </DialogFooter>
        </>
    )
}

type DatasetEditorProps = {
    // null creates a new config.
    datasetId: string | null
    onClose: () => void
    onSaved: (config: DatasetConfig) => void
}

const DatasetEditor = ({ datasetId, onClose, onSaved }: DatasetEditorProps) => {
    const { t } = useI18n()
    const existing = useQuery({
        queryKey: queryKeys.dataset(datasetId ?? ''),
        queryFn: () => datasetsApi.get(datasetId ?? ''),
        enabled: datasetId !== null,
        staleTime: 0,
        gcTime: 0
    })

    return (
        <Dialog open onOpenChange={(open) => !open && onClose()}>
            <DialogContent
                className="max-w-4xl"
                onInteractOutside={(event) => event.preventDefault()}
            >
                <DialogHeader>
                    <DialogTitle>{datasetId ? t('dataset.edit') : t('dataset.new')}</DialogTitle>
                    <DialogDescription>{t('dataset.editor.desc')}</DialogDescription>
                </DialogHeader>
                {datasetId !== null && existing.isPending ? (
                    <p className="py-10 text-center text-sm text-muted-foreground">
                        {t('common.loading')}
                    </p>
                ) : datasetId !== null && existing.isError ? (
                    <Alert variant="destructive">
                        <AlertDescription className="mt-0">
                            {getApiErrorMessage(existing.error, t('dataset.loadError'))}
                        </AlertDescription>
                    </Alert>
                ) : (
                    <EditorForm
                        datasetId={datasetId}
                        initial={
                            existing.data
                                ? configToDraft(
                                      existing.data.name,
                                      existing.data.description,
                                      existing.data.config
                                  )
                                : emptyDraft()
                        }
                        warnings={existing.data?.warnings ?? []}
                        onClose={onClose}
                        onSaved={onSaved}
                    />
                )}
            </DialogContent>
        </Dialog>
    )
}

export default DatasetEditor
