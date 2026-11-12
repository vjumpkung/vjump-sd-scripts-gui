import type {
    AccelerateRequest,
    JobRequest,
    Preset,
    SchemaArg,
    ScriptSchema,
    TrainingConfigFile
} from '@/api/types'
import { TRAINING_CONFIG_SCHEMA } from '@/api/types'
import type { I18nKey } from '@/i18n'

/*
 * The form works on strings. Numbers stay as typed text so a half-typed "1e-" never gets lost, and
 * conversion to the typed JSON of docs/api.md happens once, in `buildRequestValues`.
 */
export type FieldValue = string | boolean | string[]
export type FormValues = Record<string, FieldValue>

// Dests the backend rejects inside `values` (docs/api.md, "Command-building rules" 1).
export const GUI_OWNED_DESTS: ReadonlySet<string> = new Set([
    'config_file',
    'output_config',
    'dataset_config',
    'wandb_api_key',
    'huggingface_token',
    'log_tracker_config'
])

// List args edited as key=value rows.
export const KEY_VALUE_DESTS: ReadonlySet<string> = new Set([
    'network_args',
    'optimizer_args',
    'lr_scheduler_args'
])

export const COMMON_OPTIMIZERS = [
    'AdamW',
    'AdamW8bit',
    'PagedAdamW8bit',
    'Lion',
    'Lion8bit',
    'Prodigy',
    'DAdaptAdam',
    'AdaFactor',
    'AdamWScheduleFree',
    'RAdamScheduleFree',
    'SGDNesterov'
]

export const COMMON_SCHEDULERS = [
    'constant',
    'constant_with_warmup',
    'cosine',
    'cosine_with_restarts',
    'linear',
    'polynomial',
    'cosine_with_min_lr',
    'warmup_stable_decay',
    'adafactor'
]

export const COMBOBOX_VALUES: Record<string, string[]> = {
    optimizer_type: COMMON_OPTIMIZERS,
    lr_scheduler: COMMON_SCHEDULERS
}

// network_args written as booleans must be capitalised for these trainer modules.
export const CAPITALISED_BOOL_MODULES = [
    'lora_flux',
    'lora_sd3',
    'lora_lumina',
    'lora_hunyuan_image'
]

export const MODEL_FILE_EXTENSIONS = '.safetensors,.ckpt,.pt,.bin'

export const isKeyValueArg = (arg: SchemaArg) =>
    arg.kind === 'list' && KEY_VALUE_DESTS.has(arg.dest)

const NUMBER = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/
const INTEGER = /^[+-]?\d+$/
const INT_OR_FLOAT = /^\d+(\.\d+)?%?$/

// ---- API value <-> form value -----------------------------------------------------------------

export const toFormValue = (arg: SchemaArg, raw: unknown): FieldValue => {
    if (arg.kind === 'bool') return raw === true
    if (arg.kind === 'list') {
        const items = Array.isArray(raw)
            ? raw.map(String)
            : raw === null || raw === undefined || raw === ''
              ? []
              : String(raw).split(/\s+/)
        return isKeyValueArg(arg) ? items : items.join(' ')
    }
    if (raw === null || raw === undefined) return ''
    return String(raw)
}

// Numeric lists accept commas too; string lists (paths) split on whitespace only.
const splitItems = (text: string, arg: SchemaArg) =>
    text.split(arg.item_kind === 'str' ? /\s+/ : /[\s,]+/).filter(Boolean)

const coerceNumber = (text: string) => Number(text)

/** Typed value for the request, or undefined when the field should be omitted. */
export const toApiValue = (arg: SchemaArg, value: FieldValue | undefined): unknown => {
    if (value === undefined) return undefined

    if (arg.kind === 'bool') return value === true ? true : undefined

    if (arg.kind === 'list') {
        const items = Array.isArray(value)
            ? value.map((item) => item.trim()).filter(Boolean)
            : splitItems(String(value), arg)
        if (items.length === 0) return undefined
        if (arg.item_kind === 'int' || arg.item_kind === 'float') return items.map(coerceNumber)
        return items
    }

    const text = String(value).trim()
    if (text === '') return undefined

    if (arg.kind === 'int' || arg.kind === 'float') return coerceNumber(text)
    if (arg.kind === 'int_or_float')
        return text.endsWith('%') || !NUMBER.test(text) ? text : Number(text)
    // A str arg can still carry integer choices, such as max_token_length.
    if (arg.choices?.some((choice) => typeof choice === 'number')) {
        const numeric = Number(text)
        return Number.isFinite(numeric) ? numeric : text
    }
    return text
}

export const isEmptyValue = (value: FieldValue | undefined) => {
    if (value === undefined) return true
    if (typeof value === 'boolean') return !value
    if (Array.isArray(value)) return value.every((item) => item.trim() === '')
    return value.trim() === ''
}

// Comparison key: numbers compare by value ("1e-4" equals "0.0001"), lists ignore blank rows.
const comparable = (arg: SchemaArg, value: FieldValue | undefined): string => {
    if (value === undefined) return ''
    if (typeof value === 'boolean') return value ? 'true' : 'false'
    if (Array.isArray(value))
        return value
            .map((item) => item.trim())
            .filter(Boolean)
            .join('\u0000')

    const text = value.trim()
    const numeric = (token: string) =>
        NUMBER.test(token) && Number.isFinite(Number(token)) ? String(Number(token)) : token

    if (arg.kind === 'list') return splitItems(text, arg).map(numeric).join('\u0000')
    if (arg.kind === 'int' || arg.kind === 'float' || arg.kind === 'int_or_float')
        return numeric(text)
    return text
}

export const sameValue = (arg: SchemaArg, a: FieldValue | undefined, b: FieldValue | undefined) =>
    comparable(arg, a) === comparable(arg, b)

// ---- validation -------------------------------------------------------------------------------

export type FieldError = { key: I18nKey; vars?: Record<string, string | number> }

export const validateValue = (arg: SchemaArg, value: FieldValue | undefined): FieldError | null => {
    if (value === undefined || typeof value === 'boolean') return null

    const checkNumber = (token: string, integer: boolean): FieldError | null => {
        if (integer ? !INTEGER.test(token) : !NUMBER.test(token)) {
            return { key: integer ? 'validation.integer' : 'validation.number' }
        }
        if (arg.min !== null && Number(token) < arg.min) {
            return { key: 'validation.min', vars: { min: arg.min } }
        }
        return null
    }

    if (arg.kind === 'list') {
        if (Array.isArray(value)) return null
        const items = splitItems(value, arg)
        if (arg.item_kind === 'int' || arg.item_kind === 'float') {
            for (const item of items) {
                const error = checkNumber(item, arg.item_kind === 'int')
                if (error) return error
            }
        }
        return null
    }

    if (Array.isArray(value)) return null
    const text = value.trim()
    if (text === '') return null

    if (arg.kind === 'int') return checkNumber(text, true)
    if (arg.kind === 'float') return checkNumber(text, false)
    if (arg.kind === 'int_or_float') {
        if (!INT_OR_FLOAT.test(text)) return { key: 'validation.intOrFloat' }
        return null
    }
    if (arg.choices && !arg.choices.map(String).includes(text)) return { key: 'validation.choice' }
    return null
}

// ---- initial values, drafts and requests ------------------------------------------------------

export const buildInitialValues = (preset: Preset, schema: ScriptSchema): FormValues => {
    const values: FormValues = {}
    for (const arg of schema.args) {
        values[arg.dest] = toFormValue(
            arg,
            arg.dest in preset.defaults ? preset.defaults[arg.dest] : arg.default
        )
    }
    return values
}

export const buildSchemaDefaults = (schema: ScriptSchema): FormValues =>
    Object.fromEntries(schema.args.map((arg) => [arg.dest, toFormValue(arg, arg.default)]))

export const argMap = (schema: ScriptSchema) =>
    new Map(schema.args.map((arg) => [arg.dest, arg] as const))

const matchesType = (arg: SchemaArg, value: unknown): value is FieldValue => {
    if (arg.kind === 'bool') return typeof value === 'boolean'
    if (isKeyValueArg(arg)) return Array.isArray(value) && value.every((v) => typeof v === 'string')
    return typeof value === 'string'
}

/** Applies stored overrides, silently dropping anything the schema no longer knows. */
export const applyOverrides = (
    base: FormValues,
    overrides: Record<string, unknown>,
    schema: ScriptSchema
): FormValues => {
    const next = { ...base }
    const args = argMap(schema)
    for (const [dest, value] of Object.entries(overrides)) {
        const arg = args.get(dest)
        if (arg && matchesType(arg, value)) next[dest] = value
    }
    return next
}

export const diffOverrides = (
    values: FormValues,
    initial: FormValues,
    schema: ScriptSchema
): FormValues => {
    const overrides: FormValues = {}
    for (const arg of schema.args) {
        const value = values[arg.dest]
        if (value !== undefined && !sameValue(arg, value, initial[arg.dest])) {
            overrides[arg.dest] = value
        }
    }
    return overrides
}

/**
 * Dests that must be filled before a job can be added: the preset's own list plus any schema arg
 * that argparse marks required. LECO's prompts_file is the only such arg, and it is not in the
 * preset list; it travels as an inline file, so the backend rejects an empty one with 422.
 */
export const requiredDests = (preset: Preset, schema: ScriptSchema): string[] => [
    ...preset.required,
    ...schema.args
        .filter(
            (arg) =>
                arg.required &&
                !GUI_OWNED_DESTS.has(arg.dest) &&
                !preset.required.includes(arg.dest)
        )
        .map((arg) => arg.dest)
]

// Dests that never travel in `values`.
export const isExcludedFromValues = (preset: Preset, dest: string) =>
    GUI_OWNED_DESTS.has(dest) || dest in preset.inline_files

/**
 * Typed `values` for the request: only dests that differ from the schema default, plus every
 * dest the preset requires. Booleans that are false, empty strings and empty lists are dropped.
 */
export const buildRequestValues = (
    preset: Preset,
    schema: ScriptSchema,
    values: FormValues,
    schemaDefaults: FormValues
): Record<string, unknown> => {
    const required = new Set(preset.required)
    const out: Record<string, unknown> = {}

    for (const arg of schema.args) {
        if (isExcludedFromValues(preset, arg.dest)) continue

        const value = values[arg.dest]
        const changed = !sameValue(arg, value, schemaDefaults[arg.dest])
        if (!changed && !required.has(arg.dest)) continue

        const typed = toApiValue(arg, value)
        if (typed !== undefined) out[arg.dest] = typed
    }
    return out
}

export const buildInlineFiles = (preset: Preset, inlineFiles: Record<string, string>) => {
    const out: Record<string, string> = {}
    for (const dest of Object.keys(preset.inline_files)) {
        const text = inlineFiles[dest] ?? ''
        if (text.trim() !== '') out[dest] = text
    }
    return out
}

export type FormSnapshot = {
    name: string
    datasetConfigId: string
    values: FormValues
    inlineFiles: Record<string, string>
}

export const buildJobRequest = (
    preset: Preset,
    schema: ScriptSchema,
    schemaDefaults: FormValues,
    snapshot: FormSnapshot,
    accelerate: AccelerateRequest
): JobRequest => ({
    name: snapshot.name.trim(),
    preset_id: preset.id,
    dataset_config_id: preset.dataset_kinds.length > 0 ? snapshot.datasetConfigId || null : null,
    values: buildRequestValues(preset, schema, snapshot.values, schemaDefaults),
    inline_files: buildInlineFiles(preset, snapshot.inlineFiles),
    accelerate
})

export const buildConfigFile = (request: JobRequest): TrainingConfigFile => ({
    schema: TRAINING_CONFIG_SCHEMA,
    version: 1,
    preset_id: request.preset_id,
    name: request.name,
    values: request.values,
    inline_files: request.inline_files,
    accelerate: request.accelerate
})

export const slugify = (text: string) =>
    text
        .trim()
        .replace(/[^A-Za-z0-9._-]+/g, '_')
        .replace(/\.{2,}/g, '.')
        .replace(/^[_.-]+|[_.-]+$/g, '')
        .slice(0, 64)

// ---- drafts -----------------------------------------------------------------------------------

const DRAFT_VERSION = 1

export type Draft = {
    version: typeof DRAFT_VERSION
    name: string
    outputNameEdited: boolean
    datasetConfigId: string
    overrides: Record<string, unknown>
    inlineFiles: Record<string, string>
}

export const draftKey = (presetId: string) => `sdgui:draft:${presetId}`

export const emptyDraft = (): Draft => ({
    version: DRAFT_VERSION,
    name: '',
    outputNameEdited: false,
    datasetConfigId: '',
    overrides: {},
    inlineFiles: {}
})

const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === 'object' && value !== null && !Array.isArray(value)

export const readDraft = (presetId: string): Draft => {
    try {
        const raw = window.localStorage.getItem(draftKey(presetId))
        if (!raw) return emptyDraft()
        const parsed: unknown = JSON.parse(raw)
        if (!isRecord(parsed) || parsed.version !== DRAFT_VERSION) return emptyDraft()

        const inline: Record<string, string> = {}
        if (isRecord(parsed.inlineFiles)) {
            for (const [key, text] of Object.entries(parsed.inlineFiles)) {
                if (typeof text === 'string') inline[key] = text
            }
        }
        return {
            version: DRAFT_VERSION,
            name: typeof parsed.name === 'string' ? parsed.name : '',
            outputNameEdited: parsed.outputNameEdited === true,
            datasetConfigId:
                typeof parsed.datasetConfigId === 'string' ? parsed.datasetConfigId : '',
            overrides: isRecord(parsed.overrides) ? parsed.overrides : {},
            inlineFiles: inline
        }
    } catch {
        return emptyDraft()
    }
}

export const writeDraft = (presetId: string, draft: Draft) => {
    try {
        window.localStorage.setItem(draftKey(presetId), JSON.stringify(draft))
    } catch {
        // Storage can be unavailable (private windows, blocked site data); the live form still works.
    }
}

export const clearDraft = (presetId: string) => {
    try {
        window.localStorage.removeItem(draftKey(presetId))
    } catch {
        // Nothing to clean up when storage is unavailable.
    }
}

// ---- config import ---------------------------------------------------------------------------

export type ImportedConfig = {
    presetId: string
    name: string
    values: Record<string, unknown>
    inlineFiles: Record<string, string>
    accelerate: AccelerateRequest | null
}

export type ImportError = 'notConfig' | 'version' | 'preset' | 'values'

export const parseConfigFile = (
    parsed: unknown,
    knownPresetIds: string[]
): { ok: true; config: ImportedConfig } | { ok: false; error: ImportError } => {
    if (!isRecord(parsed) || parsed.schema !== TRAINING_CONFIG_SCHEMA) {
        return { ok: false, error: 'notConfig' }
    }
    if (parsed.version !== 1) return { ok: false, error: 'version' }
    if (typeof parsed.preset_id !== 'string' || !knownPresetIds.includes(parsed.preset_id)) {
        return { ok: false, error: 'preset' }
    }
    if (!isRecord(parsed.values)) return { ok: false, error: 'values' }

    const inlineFiles: Record<string, string> = {}
    if (isRecord(parsed.inline_files)) {
        for (const [key, text] of Object.entries(parsed.inline_files)) {
            if (typeof text === 'string') inlineFiles[key] = text
        }
    }

    let accelerate: AccelerateRequest | null = null
    if (isRecord(parsed.accelerate)) {
        const a = parsed.accelerate
        if (
            typeof a.num_processes === 'number' &&
            typeof a.num_machines === 'number' &&
            typeof a.num_cpu_threads_per_process === 'number' &&
            typeof a.dynamo_backend === 'string'
        ) {
            accelerate = {
                num_processes: a.num_processes,
                num_machines: a.num_machines,
                num_cpu_threads_per_process: a.num_cpu_threads_per_process,
                dynamo_backend: a.dynamo_backend
            }
        }
    }

    return {
        ok: true,
        config: {
            presetId: parsed.preset_id,
            name: typeof parsed.name === 'string' ? parsed.name : '',
            values: parsed.values,
            inlineFiles,
            accelerate
        }
    }
}

/** Converts imported typed values to the form representation, as draft overrides. */
export const importedOverrides = (
    values: Record<string, unknown>,
    schema: ScriptSchema
): FormValues => {
    const out: FormValues = {}
    const args = argMap(schema)
    for (const [dest, raw] of Object.entries(values)) {
        const arg = args.get(dest)
        if (arg) out[dest] = toFormValue(arg, raw)
    }
    return out
}
