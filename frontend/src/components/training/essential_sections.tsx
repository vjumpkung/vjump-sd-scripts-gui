import { type FieldValue, isKeyValueArg } from './form_state'
import SchemaField, { pathKindFor } from './schema_field'
import SectionCard, { FieldGrid } from './section_card'
import type { EssentialsSection, Preset, SchemaArg } from '@/api/types'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'
import { useId } from 'react'

// Where each inline file's textarea lives when the preset's essentials do not say.
const INLINE_HOME: Record<string, string> = { sample_prompts: 'sampling', prompts_file: 'leco' }

type InlineFileFieldProps = {
    dest: string
    filename: string
    required: boolean
    value: string
    onChange: (dest: string, text: string) => void
}

const InlineFileField = ({ dest, filename, required, value, onChange }: InlineFileFieldProps) => {
    const { t, lookup } = useI18n()
    const id = useId()
    const helpId = `${id}-help`

    const label = lookup(`inline.${dest}.label`) ?? lookup(`fields.${dest}.label`) ?? dest
    const help = lookup(`inline.${dest}.help`) ?? lookup(`fields.${dest}.help`) ?? ''
    const placeholder = lookup(`inline.${dest}.placeholder`)

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
            <code className="font-mono text-xs text-muted-foreground" translate="no">
                --{dest} → {filename}
            </code>
            <Textarea
                id={id}
                rows={8}
                value={value}
                spellCheck={false}
                translate="no"
                placeholder={placeholder}
                aria-describedby={helpId}
                className="font-mono"
                onChange={(event) => onChange(dest, event.target.value)}
            />
            <p id={helpId} className="text-[0.8125rem] leading-relaxed text-muted-foreground">
                {help} {t('inline.savedWithJob')}
            </p>
        </div>
    )
}

type EssentialSectionsProps = {
    preset: Preset
    required: string[]
    args: Map<string, SchemaArg>
    values: Record<string, FieldValue>
    initial: Record<string, FieldValue>
    schemaDefaults: Record<string, FieldValue>
    modelDests: ReadonlySet<string>
    onChange: (dest: string, value: FieldValue) => void
    inlineFiles: Record<string, string>
    onInlineChange: (dest: string, text: string) => void
}

// Shown in the Project section instead of in a section of their own.
const PROJECT_DESTS: ReadonlySet<string> = new Set(['output_name', 'output_dir'])

const EssentialSections = ({
    preset,
    required,
    args,
    values,
    initial,
    schemaDefaults,
    modelDests,
    onChange,
    inlineFiles,
    onInlineChange
}: EssentialSectionsProps) => {
    const { lookup } = useI18n()
    const inlineDests = Object.keys(preset.inline_files)

    const sections: EssentialsSection[] = preset.essentials.map((section) => ({ ...section }))
    for (const dest of inlineDests) {
        const home = INLINE_HOME[dest] ?? 'sampling'
        if (!sections.some((section) => section.id === home)) sections.push({ id: home, dests: [] })
    }

    const seen = new Set<string>()

    return (
        <>
            {sections.map((section) => {
                const dests = section.dests.filter((dest) => {
                    if (seen.has(dest)) return false
                    if (!args.has(dest)) return false
                    if (modelDests.has(dest) || PROJECT_DESTS.has(dest)) return false
                    if (dest in preset.inline_files) return false
                    seen.add(dest)
                    return true
                })
                const inline = inlineDests.filter(
                    (dest) => (INLINE_HOME[dest] ?? 'sampling') === section.id
                )
                if (dests.length === 0 && inline.length === 0) return null

                return (
                    <SectionCard
                        key={section.id}
                        title={lookup(`essentials.${section.id}`) ?? section.id}
                        description={lookup(`essentials.${section.id}.desc`)}
                    >
                        <FieldGrid>
                            {dests.map((dest) => {
                                const arg = args.get(dest)
                                if (!arg) return null
                                return (
                                    <div
                                        key={dest}
                                        className={cn(
                                            'min-w-0',
                                            isKeyValueArg(arg) && 'md:col-span-2'
                                        )}
                                    >
                                        <SchemaField
                                            arg={arg}
                                            value={values[dest] ?? ''}
                                            resetValue={initial[dest] ?? ''}
                                            schemaDefault={schemaDefaults[dest] ?? ''}
                                            pathKind={pathKindFor(arg, modelDests)}
                                            required={required.includes(dest)}
                                            networkModule={
                                                dest === 'network_args'
                                                    ? String(values.network_module ?? '')
                                                    : undefined
                                            }
                                            onChange={onChange}
                                        />
                                    </div>
                                )
                            })}
                            {inline.map((dest) => (
                                <InlineFileField
                                    key={dest}
                                    dest={dest}
                                    filename={preset.inline_files[dest]}
                                    required={required.includes(dest)}
                                    value={inlineFiles[dest] ?? ''}
                                    onChange={onInlineChange}
                                />
                            ))}
                        </FieldGrid>
                    </SectionCard>
                )
            })}
        </>
    )
}

export default EssentialSections
