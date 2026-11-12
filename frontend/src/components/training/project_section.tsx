import { type FieldValue } from './form_state'
import SchemaField, { pathKindFor } from './schema_field'
import SectionCard, { FieldGrid } from './section_card'
import type { DatasetSummary, Preset, SchemaArg } from '@/api/types'
import { kindTone } from '@/components/kind_tone'
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
import useMenuBar from '@/hooks/useMenubar'
import { useI18n } from '@/i18n'
import { useId } from 'react'

type ProjectSectionProps = {
    preset: Preset
    required: string[]
    args: Map<string, SchemaArg>
    name: string
    onNameChange: (name: string) => void
    values: Record<string, FieldValue>
    initial: Record<string, FieldValue>
    schemaDefaults: Record<string, FieldValue>
    onChange: (dest: string, value: FieldValue) => void
    datasets: DatasetSummary[]
    datasetsLoading: boolean
    datasetConfigId: string
    onDatasetChange: (id: string) => void
}

const ProjectSection = ({
    preset,
    required,
    args,
    name,
    onNameChange,
    values,
    initial,
    schemaDefaults,
    onChange,
    datasets,
    datasetsLoading,
    datasetConfigId,
    onDatasetChange
}: ProjectSectionProps) => {
    const { t } = useI18n()
    const go = useMenuBar((state) => state.go)
    const nameId = useId()
    const datasetId = useId()
    const datasetHintId = useId()
    const noModelDests: ReadonlySet<string> = new Set()
    const needsDataset = preset.dataset_kinds.length > 0

    const compatible = datasets.filter((dataset) =>
        dataset.kinds.every((kind) => preset.dataset_kinds.includes(kind))
    )
    const selected = compatible.find((dataset) => dataset.id === datasetConfigId)

    const field = (dest: string) => {
        const arg = args.get(dest)
        if (!arg) return null
        return (
            <SchemaField
                arg={arg}
                value={values[dest] ?? ''}
                resetValue={initial[dest] ?? ''}
                schemaDefault={schemaDefaults[dest] ?? ''}
                pathKind={pathKindFor(arg, noModelDests)}
                required={required.includes(dest)}
                onChange={onChange}
            />
        )
    }

    return (
        <SectionCard title={t('section.project')} description={t('section.project.desc')}>
            <FieldGrid>
                <div className="flex min-w-0 flex-col gap-2">
                    <Label htmlFor={nameId} className="text-sm font-semibold">
                        {t('project.name')}
                        <span aria-hidden className="text-pink-ink">
                            *
                        </span>
                    </Label>
                    <code className="font-mono text-xs text-muted-foreground" translate="no">
                        name
                    </code>
                    <Input
                        id={nameId}
                        value={name}
                        autoComplete="off"
                        maxLength={120}
                        onChange={(event) => onNameChange(event.target.value)}
                    />
                    <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">
                        {t('project.name.help')}
                    </p>
                </div>
                {field('output_name')}
                {field('output_dir')}

                {needsDataset ? (
                    <div className="flex min-w-0 flex-col gap-2">
                        <Label htmlFor={datasetId} className="text-sm font-semibold">
                            {t('project.dataset')}
                            <span aria-hidden className="text-pink-ink">
                                *
                            </span>
                        </Label>
                        <Select
                            value={selected?.id ?? ''}
                            onValueChange={onDatasetChange}
                            disabled={compatible.length === 0}
                        >
                            <SelectTrigger
                                id={datasetId}
                                aria-describedby={datasetHintId}
                                aria-required
                            >
                                <SelectValue
                                    placeholder={
                                        datasetsLoading
                                            ? t('common.loading')
                                            : t('project.dataset.placeholder')
                                    }
                                />
                            </SelectTrigger>
                            <SelectContent>
                                {compatible.map((dataset) => (
                                    <SelectItem key={dataset.id} value={dataset.id}>
                                        {dataset.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <div
                            id={datasetHintId}
                            className="flex flex-wrap items-center gap-2 text-[0.8125rem] leading-relaxed text-muted-foreground"
                        >
                            <span>{t('project.dataset.accepts')}</span>
                            {preset.dataset_kinds.map((kind) => (
                                <Badge key={kind} variant={kindTone[kind]}>
                                    {t(`kind.${kind}`)}
                                </Badge>
                            ))}
                        </div>
                        {!datasetsLoading && compatible.length === 0 ? (
                            <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">
                                {t('project.dataset.none')}{' '}
                                <Button variant="link" onClick={() => go('datasets')}>
                                    {t('project.dataset.open')}
                                </Button>
                            </p>
                        ) : null}
                    </div>
                ) : null}
            </FieldGrid>
        </SectionCard>
    )
}

export default ProjectSection
