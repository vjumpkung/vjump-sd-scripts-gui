import type { DatasetConfigBody, DatasetKind } from '@/api/types'
import type { I18nKey } from '@/i18n'
import { formatAdditionalOptions, parseAdditionalOptions } from '@/lib/toml'

/*
 * The dataset editor works on strings so half-typed numbers survive. `draftToConfig` turns the
 * draft into the sd-scripts dataset structure ([general], [[datasets]], [[datasets.subsets]]) and
 * `configToDraft` reads a stored config back, putting any key without its own input into the
 * "Additional TOML options" text.
 */

// '' leaves the key out so the sd-scripts default (or the parent level) applies.
export type TriState = '' | 'true' | 'false'

export type GeneralDraft = {
    shuffle_caption: TriState
    caption_extension: string
    keep_tokens: string
    flip_aug: TriState
    color_aug: TriState
    random_crop: TriState
    caption_dropout_rate: string
    additional: string
}

export type SubsetDraft = {
    uid: string
    kind: DatasetKind
    image_dir: string
    metadata_file: string
    conditioning_data_dir: string
    num_repeats: string
    class_tokens: string
    caption_extension: string
    is_reg: TriState
    keep_tokens: string
    shuffle_caption: TriState
    flip_aug: TriState
    additional: string
}

export type DatasetDraft = {
    uid: string
    width: string
    height: string
    batch_size: string
    enable_bucket: TriState
    min_bucket_reso: string
    max_bucket_reso: string
    bucket_reso_steps: string
    bucket_no_upscale: TriState
    additional: string
    subsets: SubsetDraft[]
}

export type EditorDraft = {
    name: string
    description: string
    general: GeneralDraft
    datasets: DatasetDraft[]
}

export type DraftIssue = { key: I18nKey; vars?: Record<string, string | number> }

let counter = 0
const nextUid = () => `d${(counter += 1)}`

export const emptySubset = (kind: DatasetKind = 'dreambooth'): SubsetDraft => ({
    uid: nextUid(),
    kind,
    image_dir: '',
    metadata_file: '',
    conditioning_data_dir: '',
    num_repeats: '',
    class_tokens: '',
    caption_extension: '',
    is_reg: '',
    keep_tokens: '',
    shuffle_caption: '',
    flip_aug: '',
    additional: ''
})

export const emptyDataset = (): DatasetDraft => ({
    uid: nextUid(),
    width: '1024',
    height: '1024',
    batch_size: '1',
    enable_bucket: 'true',
    min_bucket_reso: '',
    max_bucket_reso: '',
    bucket_reso_steps: '',
    bucket_no_upscale: '',
    additional: '',
    subsets: [emptySubset()]
})

// Image-folder captions are .txt sidecars, but sd-scripts' own default extension is .caption,
// so a new config starts with .txt or the captions would be ignored.
export const emptyGeneral = (): GeneralDraft => ({
    shuffle_caption: '',
    caption_extension: '.txt',
    keep_tokens: '',
    flip_aug: '',
    color_aug: '',
    random_crop: '',
    caption_dropout_rate: '',
    additional: ''
})

export const emptyDraft = (): EditorDraft => ({
    name: '',
    description: '',
    general: emptyGeneral(),
    datasets: [emptyDataset()]
})

// ---- config -> draft --------------------------------------------------------------------------

const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === 'object' && value !== null && !Array.isArray(value)

const text = (value: unknown) =>
    value === undefined || value === null ? '' : typeof value === 'string' ? value : String(value)

const tri = (value: unknown): TriState => (value === true ? 'true' : value === false ? 'false' : '')

const rest = (source: Record<string, unknown>, known: readonly string[]) =>
    formatAdditionalOptions(
        Object.fromEntries(Object.entries(source).filter(([key]) => !known.includes(key)))
    )

const GENERAL_KEYS = [
    'shuffle_caption',
    'caption_extension',
    'keep_tokens',
    'flip_aug',
    'color_aug',
    'random_crop',
    'caption_dropout_rate'
] as const

const DATASET_KEYS = [
    'resolution',
    'batch_size',
    'enable_bucket',
    'min_bucket_reso',
    'max_bucket_reso',
    'bucket_reso_steps',
    'bucket_no_upscale',
    'subsets'
] as const

const SUBSET_KEYS = [
    'image_dir',
    'metadata_file',
    'conditioning_data_dir',
    'num_repeats',
    'class_tokens',
    'caption_extension',
    'is_reg',
    'keep_tokens',
    'shuffle_caption',
    'flip_aug'
] as const

export const subsetKind = (subset: Record<string, unknown>): DatasetKind =>
    'metadata_file' in subset
        ? 'finetune'
        : 'conditioning_data_dir' in subset
          ? 'controlnet'
          : 'dreambooth'

export const configToDraft = (
    name: string,
    description: string,
    config: DatasetConfigBody
): EditorDraft => {
    const general = isRecord(config.general) ? config.general : {}

    const datasets = (Array.isArray(config.datasets) ? config.datasets : []).map((raw) => {
        const dataset = isRecord(raw) ? raw : {}
        const resolution = dataset.resolution
        const [width, height] = Array.isArray(resolution)
            ? [text(resolution[0]), text(resolution[1])]
            : [text(resolution), text(resolution)]
        const subsets = (Array.isArray(dataset.subsets) ? dataset.subsets : []).map((item) => {
            const subset = isRecord(item) ? item : {}
            return {
                uid: nextUid(),
                kind: subsetKind(subset),
                image_dir: text(subset.image_dir),
                metadata_file: text(subset.metadata_file),
                conditioning_data_dir: text(subset.conditioning_data_dir),
                num_repeats: text(subset.num_repeats),
                class_tokens: text(subset.class_tokens),
                caption_extension: text(subset.caption_extension),
                is_reg: tri(subset.is_reg),
                keep_tokens: text(subset.keep_tokens),
                shuffle_caption: tri(subset.shuffle_caption),
                flip_aug: tri(subset.flip_aug),
                additional: rest(subset, SUBSET_KEYS)
            } satisfies SubsetDraft
        })
        return {
            uid: nextUid(),
            width,
            height,
            batch_size: text(dataset.batch_size),
            enable_bucket: tri(dataset.enable_bucket),
            min_bucket_reso: text(dataset.min_bucket_reso),
            max_bucket_reso: text(dataset.max_bucket_reso),
            bucket_reso_steps: text(dataset.bucket_reso_steps),
            bucket_no_upscale: tri(dataset.bucket_no_upscale),
            additional: rest(dataset, DATASET_KEYS),
            subsets: subsets.length > 0 ? subsets : [emptySubset()]
        } satisfies DatasetDraft
    })

    return {
        name,
        description,
        general: {
            shuffle_caption: tri(general.shuffle_caption),
            caption_extension: text(general.caption_extension),
            keep_tokens: text(general.keep_tokens),
            flip_aug: tri(general.flip_aug),
            color_aug: tri(general.color_aug),
            random_crop: tri(general.random_crop),
            caption_dropout_rate: text(general.caption_dropout_rate),
            additional: rest(general, GENERAL_KEYS)
        },
        datasets: datasets.length > 0 ? datasets : [emptyDataset()]
    }
}

// ---- draft -> config --------------------------------------------------------------------------

const INTEGER = /^[+-]?\d+$/
const NUMBER = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/

type Collector = { issues: DraftIssue[] }

const optionalBool = (value: TriState): boolean | undefined =>
    value === '' ? undefined : value === 'true'

const optionalString = (value: string): string | undefined => {
    const trimmed = value.trim()
    return trimmed === '' ? undefined : trimmed
}

const optionalNumber = (
    value: string,
    kind: 'int' | 'float',
    label: I18nKey,
    collector: Collector,
    min?: number
): number | undefined => {
    const trimmed = value.trim()
    if (trimmed === '') return undefined
    const valid = kind === 'int' ? INTEGER.test(trimmed) : NUMBER.test(trimmed)
    if (!valid) {
        collector.issues.push({ key: 'dataset.issue.number', vars: { field: label } })
        return undefined
    }
    const parsed = Number(trimmed)
    if (min !== undefined && parsed < min) {
        collector.issues.push({ key: 'dataset.issue.min', vars: { field: label, min } })
        return undefined
    }
    return parsed
}

const additional = (
    value: string,
    where: string,
    collector: Collector
): Record<string, unknown> => {
    const result = parseAdditionalOptions(value)
    if (result.ok) return result.values
    collector.issues.push({
        key: 'dataset.issue.additional',
        vars: { where, line: result.line }
    })
    return {}
}

const clean = (source: Record<string, unknown>) =>
    Object.fromEntries(Object.entries(source).filter(([, value]) => value !== undefined))

export const draftToConfig = (
    draft: EditorDraft
): { config: DatasetConfigBody; issues: DraftIssue[] } => {
    const collector: Collector = { issues: [] }
    const g = draft.general

    const general = clean({
        ...additional(g.additional, 'general', collector),
        shuffle_caption: optionalBool(g.shuffle_caption),
        caption_extension: optionalString(g.caption_extension),
        keep_tokens: optionalNumber(g.keep_tokens, 'int', 'dataset.field.keepTokens', collector, 0),
        flip_aug: optionalBool(g.flip_aug),
        color_aug: optionalBool(g.color_aug),
        random_crop: optionalBool(g.random_crop),
        caption_dropout_rate: optionalNumber(
            g.caption_dropout_rate,
            'float',
            'dataset.field.captionDropout',
            collector,
            0
        )
    })

    const datasets = draft.datasets.map((dataset, datasetIndex) => {
        const where = `datasets[${datasetIndex + 1}]`
        const width = optionalNumber(dataset.width, 'int', 'dataset.field.width', collector, 1)
        const height = optionalNumber(dataset.height, 'int', 'dataset.field.height', collector, 1)
        // sd-scripts has no default resolution, so a dataset without one cannot train.
        if (dataset.width.trim() === '' || dataset.height.trim() === '') {
            collector.issues.push({ key: 'dataset.issue.resolution', vars: { where } })
        }

        const subsets = dataset.subsets.map((subset, subsetIndex) => {
            const subsetWhere = `${where}.subsets[${subsetIndex + 1}]`
            if (optionalString(subset.image_dir) === undefined && subset.kind !== 'finetune') {
                collector.issues.push({
                    key: 'dataset.issue.imageDir',
                    vars: { where: subsetWhere }
                })
            }
            if (subset.kind === 'finetune' && optionalString(subset.metadata_file) === undefined) {
                collector.issues.push({
                    key: 'dataset.issue.metadata',
                    vars: { where: subsetWhere }
                })
            }
            if (
                subset.kind === 'controlnet' &&
                optionalString(subset.conditioning_data_dir) === undefined
            ) {
                collector.issues.push({
                    key: 'dataset.issue.conditioning',
                    vars: { where: subsetWhere }
                })
            }

            return clean({
                ...additional(subset.additional, subsetWhere, collector),
                image_dir: optionalString(subset.image_dir),
                metadata_file:
                    subset.kind === 'finetune' ? optionalString(subset.metadata_file) : undefined,
                conditioning_data_dir:
                    subset.kind === 'controlnet'
                        ? optionalString(subset.conditioning_data_dir)
                        : undefined,
                num_repeats: optionalNumber(
                    subset.num_repeats,
                    'int',
                    'dataset.field.numRepeats',
                    collector,
                    1
                ),
                class_tokens:
                    subset.kind === 'dreambooth' ? optionalString(subset.class_tokens) : undefined,
                caption_extension:
                    subset.kind === 'finetune'
                        ? undefined
                        : optionalString(subset.caption_extension),
                is_reg: subset.kind === 'dreambooth' ? optionalBool(subset.is_reg) : undefined,
                keep_tokens: optionalNumber(
                    subset.keep_tokens,
                    'int',
                    'dataset.field.keepTokens',
                    collector,
                    0
                ),
                shuffle_caption: optionalBool(subset.shuffle_caption),
                flip_aug: optionalBool(subset.flip_aug)
            })
        })

        return clean({
            ...additional(dataset.additional, where, collector),
            resolution: width !== undefined && height !== undefined ? [width, height] : undefined,
            batch_size: optionalNumber(
                dataset.batch_size,
                'int',
                'dataset.field.batchSize',
                collector,
                1
            ),
            enable_bucket: optionalBool(dataset.enable_bucket),
            min_bucket_reso: optionalNumber(
                dataset.min_bucket_reso,
                'int',
                'dataset.field.minBucket',
                collector,
                1
            ),
            max_bucket_reso: optionalNumber(
                dataset.max_bucket_reso,
                'int',
                'dataset.field.maxBucket',
                collector,
                1
            ),
            bucket_reso_steps: optionalNumber(
                dataset.bucket_reso_steps,
                'int',
                'dataset.field.bucketSteps',
                collector,
                1
            ),
            bucket_no_upscale: optionalBool(dataset.bucket_no_upscale),
            subsets
        })
    })

    return {
        config: {
            ...(Object.keys(general).length > 0 ? { general } : {}),
            datasets
        },
        issues: collector.issues
    }
}
