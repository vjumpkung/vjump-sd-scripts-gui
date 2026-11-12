import { type FieldValue, isExcludedFromValues, isKeyValueArg, sameValue } from './form_state'
import SchemaField, { pathKindFor } from './schema_field'
import SectionCard from './section_card'
import type { Preset, ScriptSchema, SchemaArg } from '@/api/types'
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger
} from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'
import { SearchIcon, XIcon } from 'lucide-react'
import { useDeferredValue, useId, useMemo, useState } from 'react'

type AllParametersProps = {
    preset: Preset
    required: string[]
    schema: ScriptSchema
    values: Record<string, FieldValue>
    initial: Record<string, FieldValue>
    schemaDefaults: Record<string, FieldValue>
    modelDests: ReadonlySet<string>
    onChange: (dest: string, value: FieldValue) => void
}

const AllParameters = ({
    preset,
    required,
    schema,
    values,
    initial,
    schemaDefaults,
    modelDests,
    onChange
}: AllParametersProps) => {
    const { t, lookup } = useI18n()
    const searchId = useId()
    const modifiedId = useId()
    const [query, setQuery] = useState('')
    const [modifiedOnly, setModifiedOnly] = useState(false)
    const [open, setOpen] = useState<string[]>([])
    const deferredQuery = useDeferredValue(query)

    // Every schema arg except the ones the backend rejects inside `values`.
    const editable = useMemo(
        () => schema.args.filter((arg) => !isExcludedFromValues(preset, arg.dest)),
        [preset, schema]
    )

    const matches = (arg: SchemaArg, needle: string) => {
        if (!needle) return true
        const label = lookup(`fields.${arg.dest}.label`) ?? ''
        const help = lookup(`fields.${arg.dest}.help`) ?? arg.help_en ?? ''
        return [arg.dest, arg.flag, label, help].some((text) => text.toLowerCase().includes(needle))
    }

    const needle = deferredQuery.trim().toLowerCase()
    const filterActive = needle !== '' || modifiedOnly
    const modifiedCount = editable.filter(
        (arg) => !sameValue(arg, values[arg.dest], schemaDefaults[arg.dest])
    ).length

    const groups = useMemo(() => {
        const byGroup = new Map<string, SchemaArg[]>()
        for (const arg of editable) {
            const list = byGroup.get(arg.group)
            if (list) list.push(arg)
            else byGroup.set(arg.group, [arg])
        }
        return byGroup
    }, [editable])

    const visible = new Map<string, SchemaArg[]>()
    for (const [group, args] of groups) {
        const shown = args.filter(
            (arg) =>
                matches(arg, needle) &&
                (!modifiedOnly || !sameValue(arg, values[arg.dest], schemaDefaults[arg.dest]))
        )
        if (shown.length > 0) visible.set(group, shown)
    }

    const openGroups = filterActive ? [...visible.keys()] : open

    return (
        <SectionCard title={t('section.all')} description={t('section.all.desc')}>
            <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center">
                <div className="relative flex-1">
                    <SearchIcon
                        aria-hidden
                        className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
                    />
                    <Input
                        id={searchId}
                        type="search"
                        value={query}
                        placeholder={t('all.search')}
                        aria-label={t('all.search')}
                        autoComplete="off"
                        spellCheck={false}
                        className="pr-12 pl-10 [&::-webkit-search-cancel-button]:hidden"
                        onChange={(event) => setQuery(event.target.value)}
                    />
                    {query ? (
                        <Button
                            variant="ghost"
                            size="icon"
                            className="absolute top-0.5 right-0.5 hover:bg-brand-pink hover:text-ink"
                            aria-label={t('common.clear')}
                            onClick={() => setQuery('')}
                        >
                            <XIcon />
                        </Button>
                    ) : null}
                </div>
                <label
                    htmlFor={modifiedId}
                    className="flex min-h-10 cursor-pointer items-center gap-3 text-sm font-medium"
                >
                    <Switch
                        id={modifiedId}
                        checked={modifiedOnly}
                        onCheckedChange={setModifiedOnly}
                    />
                    {t('all.modifiedOnly')}
                    <Badge variant="muted">{modifiedCount}</Badge>
                </label>
            </div>

            <p className="mb-2 text-sm text-muted-foreground" role="status" aria-live="polite">
                {t('all.count', {
                    shown: [...visible.values()].reduce((sum, list) => sum + list.length, 0),
                    total: editable.length
                })}
            </p>

            {visible.size === 0 ? (
                <p className="rounded-lg border border-dashed border-border px-4 py-12 text-center text-sm text-muted-foreground">
                    {t('all.empty')}
                </p>
            ) : (
                <Accordion type="multiple" value={openGroups} onValueChange={setOpen}>
                    {[...visible.entries()].map(([group, args]) => (
                        <AccordionItem key={group} value={group}>
                            <AccordionTrigger>
                                <span className="flex min-w-0 flex-wrap items-center gap-2">
                                    <span>{lookup(`group.${group}`) ?? group}</span>
                                    <Badge variant="muted">{args.length}</Badge>
                                </span>
                            </AccordionTrigger>
                            <AccordionContent>
                                <div className="grid gap-x-6 gap-y-7 pt-2 md:grid-cols-2">
                                    {args.map((arg) => (
                                        <div
                                            key={arg.dest}
                                            className={cn(
                                                'min-w-0',
                                                isKeyValueArg(arg) && 'md:col-span-2'
                                            )}
                                        >
                                            <SchemaField
                                                arg={arg}
                                                value={values[arg.dest] ?? ''}
                                                resetValue={initial[arg.dest] ?? ''}
                                                schemaDefault={schemaDefaults[arg.dest] ?? ''}
                                                pathKind={pathKindFor(arg, modelDests)}
                                                required={required.includes(arg.dest)}
                                                networkModule={
                                                    arg.dest === 'network_args'
                                                        ? String(values.network_module ?? '')
                                                        : undefined
                                                }
                                                onChange={onChange}
                                            />
                                        </div>
                                    ))}
                                </div>
                            </AccordionContent>
                        </AccordionItem>
                    ))}
                </Accordion>
            )}
        </SectionCard>
    )
}

export default AllParameters
