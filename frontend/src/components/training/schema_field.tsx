import {
    CAPITALISED_BOOL_MODULES,
    COMBOBOX_VALUES,
    type FieldValue,
    MODEL_FILE_EXTENSIONS,
    isKeyValueArg,
    sameValue,
    validateValue
} from './form_state'
import KeyValueEditor from './key_value_editor'
import type { SchemaArg } from '@/api/types'
import PathInput from '@/components/path_input'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import type { PathMode } from '@/components/workspace_browser'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'
import { ChevronDownIcon, RotateCcwIcon } from 'lucide-react'
import { type ReactNode, memo, useId } from 'react'

const UNSET = '__unset__'

// Args that hold a model or weights file. Everything else path-like is found by name.
const FILE_DESTS: ReadonlySet<string> = new Set([
    'vae',
    'weights',
    'network_weights',
    'clip_l',
    'clip_g',
    't5xxl',
    'ae',
    'gemma2',
    'qwen3',
    'text_encoder',
    'byt5',
    'llm_adapter_path',
    'controlnet_model_name_or_path',
    'pretrained_model_name_or_path'
])

// These accept either a single file or a Diffusers / sharded folder.
const FILE_OR_FOLDER_DESTS: ReadonlySet<string> = new Set([
    'pretrained_model_name_or_path',
    'qwen3',
    'text_encoder',
    'controlnet_model_name_or_path'
])

export type PathKind = { mode: PathMode; extensions?: string }

/** Decides whether an arg is edited as a path, and how it is browsed. */
export const pathKindFor = (arg: SchemaArg, modelDests: ReadonlySet<string>): PathKind | null => {
    if (arg.kind !== 'str' || arg.choices) return null
    const { dest } = arg

    if (FILE_OR_FOLDER_DESTS.has(dest)) return { mode: 'any', extensions: MODEL_FILE_EXTENSIONS }
    if (modelDests.has(dest) || FILE_DESTS.has(dest)) {
        return { mode: 'file', extensions: MODEL_FILE_EXTENSIONS }
    }
    if (/_dir$/.test(dest) || dest === 'resume' || /nvme_path$/.test(dest)) {
        return { mode: 'folder' }
    }
    if (/_(path|file)$/.test(dest) || /_name_or_path$/.test(dest)) return { mode: 'file' }
    return null
}

type SchemaFieldProps = {
    arg: SchemaArg
    value: FieldValue
    // The value the form started with (schema default overlaid with the preset default).
    resetValue: FieldValue
    schemaDefault: FieldValue
    onChange: (dest: string, value: FieldValue) => void
    pathKind: PathKind | null
    // Only network_args uses this, to stress the capitalised-boolean rule.
    networkModule?: string
    required?: boolean
    // Extra controls shown under the input, such as "Use suggested" on model files.
    footer?: ReactNode
}

type ComboboxProps = {
    id: string
    value: string
    options: string[]
    describedBy?: string
    placeholder?: string
    invalid: boolean
    onChange: (value: string) => void
}

/** Free text plus a menu of common values. */
const Combobox = ({
    id,
    value,
    options,
    describedBy,
    placeholder,
    invalid,
    onChange
}: ComboboxProps) => {
    const { t } = useI18n()

    return (
        <div className="flex gap-2">
            <Input
                id={id}
                value={value}
                spellCheck={false}
                autoComplete="off"
                translate="no"
                placeholder={placeholder}
                aria-invalid={invalid || undefined}
                aria-describedby={describedBy}
                className="font-mono"
                onChange={(event) => onChange(event.target.value)}
            />
            {/* Controlled to "" so the same common value can be picked again after typing. */}
            <Select value="" onValueChange={onChange}>
                <SelectTrigger
                    aria-label={t('field.commonValues')}
                    title={t('field.commonValues')}
                    className="w-11 shrink-0 justify-center px-0 [&>svg:last-child]:hidden"
                >
                    <ChevronDownIcon />
                </SelectTrigger>
                <SelectContent align="end" className="max-h-72">
                    {options.map((option) => (
                        <SelectItem key={option} value={option}>
                            <span translate="no">{option}</span>
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    )
}

const SchemaField = ({
    arg,
    value,
    resetValue,
    schemaDefault,
    onChange,
    pathKind,
    networkModule,
    required,
    footer
}: SchemaFieldProps) => {
    const { t, lookup } = useI18n()
    const uid = useId()
    const inputId = `${uid}-input`
    const helpId = `${uid}-help`
    const errorId = `${uid}-error`

    const label = lookup(`fields.${arg.dest}.label`) ?? arg.dest
    const help = lookup(`fields.${arg.dest}.help`) ?? arg.help_en ?? ''
    const modified = !sameValue(arg, value, schemaDefault)
    const canReset = !sameValue(arg, value, resetValue)
    const error = validateValue(arg, value)
    const describedBy =
        [help ? helpId : '', error ? errorId : ''].filter(Boolean).join(' ') || undefined
    const placeholder =
        schemaDefault !== '' && typeof schemaDefault === 'string' ? schemaDefault : undefined
    const set = (next: FieldValue) => onChange(arg.dest, next)

    const resetButton = canReset ? (
        <Button
            variant="ghost"
            size="icon"
            className="-my-2 shrink-0"
            aria-label={`${t('field.reset')}: ${label}`}
            title={t('field.reset')}
            onClick={() => set(resetValue)}
        >
            <RotateCcwIcon />
        </Button>
    ) : null

    const heading = (
        <>
            <Label htmlFor={inputId} className="text-sm font-semibold">
                <span>{label}</span>
                {required ? (
                    <span aria-hidden className="text-pink-ink">
                        *
                    </span>
                ) : null}
            </Label>
            {modified ? <Badge variant="modified">{t('field.modified')}</Badge> : null}
        </>
    )

    const flagLine = (
        <code className="font-mono text-xs break-all text-muted-foreground" translate="no">
            {arg.flag}
        </code>
    )

    const notes = (
        <>
            {help ? (
                <p id={helpId} className="text-[0.8125rem] leading-relaxed text-muted-foreground">
                    {help}
                </p>
            ) : null}
            {error ? (
                <p id={errorId} role="alert" className="text-sm text-destructive">
                    {t(error.key, error.vars)}
                </p>
            ) : null}
        </>
    )

    if (arg.kind === 'bool') {
        return (
            <div className="flex min-w-0 items-start gap-3" data-dest={arg.dest}>
                <Switch
                    id={inputId}
                    checked={value === true}
                    aria-describedby={describedBy}
                    className="mt-0.5"
                    onCheckedChange={set}
                />
                <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                    <div className="flex flex-wrap items-center gap-2">{heading}</div>
                    {flagLine}
                    {notes}
                </div>
                {resetButton}
            </div>
        )
    }

    let control
    if (arg.choices) {
        const current = typeof value === 'string' ? value : ''
        const choices = arg.choices.map(String)
        const allowUnset = arg.default === null || arg.default === undefined || current === ''
        control = (
            <Select
                value={current === '' ? UNSET : current}
                onValueChange={(next) => set(next === UNSET ? '' : next)}
            >
                <SelectTrigger
                    id={inputId}
                    aria-describedby={describedBy}
                    aria-invalid={Boolean(error) || undefined}
                >
                    <SelectValue />
                </SelectTrigger>
                <SelectContent className="max-h-72">
                    {allowUnset ? <SelectItem value={UNSET}>{t('field.unset')}</SelectItem> : null}
                    {current !== '' && !choices.includes(current) ? (
                        <SelectItem value={current}>{current}</SelectItem>
                    ) : null}
                    {choices.map((choice) => (
                        <SelectItem key={choice} value={choice}>
                            <span translate="no">{choice}</span>
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        )
    } else if (isKeyValueArg(arg)) {
        const hint =
            arg.dest === 'network_args' ? (
                <p
                    className={cn(
                        'text-[0.8125rem] leading-relaxed text-muted-foreground',
                        networkModule &&
                            CAPITALISED_BOOL_MODULES.some((name) => networkModule.endsWith(name)) &&
                            'font-medium text-foreground'
                    )}
                >
                    {t('field.networkArgsBoolHint')}
                </p>
            ) : null
        control = (
            <>
                <KeyValueEditor
                    id={inputId}
                    items={Array.isArray(value) ? value : []}
                    describedBy={describedBy}
                    onChange={set}
                />
                {hint}
            </>
        )
    } else if (pathKind) {
        control = (
            <PathInput
                id={inputId}
                value={typeof value === 'string' ? value : ''}
                mode={pathKind.mode}
                extensions={pathKind.extensions}
                invalid={Boolean(error)}
                describedBy={describedBy}
                onChange={set}
            />
        )
    } else if (COMBOBOX_VALUES[arg.dest]) {
        control = (
            <Combobox
                id={inputId}
                value={typeof value === 'string' ? value : ''}
                options={COMBOBOX_VALUES[arg.dest]}
                describedBy={describedBy}
                placeholder={placeholder}
                invalid={Boolean(error)}
                onChange={set}
            />
        )
    } else {
        const numeric = arg.kind === 'int' || arg.kind === 'float'
        control = (
            <Input
                id={inputId}
                value={typeof value === 'string' ? value : ''}
                inputMode={numeric ? 'decimal' : undefined}
                spellCheck={false}
                autoComplete="off"
                translate="no"
                placeholder={placeholder}
                aria-invalid={Boolean(error) || undefined}
                aria-describedby={describedBy}
                className={cn(arg.kind !== 'str' && 'font-mono')}
                onChange={(event) => set(event.target.value)}
            />
        )
    }

    return (
        <div className="flex min-w-0 flex-col gap-2" data-dest={arg.dest}>
            <div className="flex flex-wrap items-center gap-2">
                {heading}
                <span className="ml-auto" />
                {resetButton}
            </div>
            {flagLine}
            {control}
            {footer}
            {notes}
        </div>
    )
}

export default memo(SchemaField)
