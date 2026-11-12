import { type FieldValue } from './form_state'
import SchemaField, { pathKindFor } from './schema_field'
import SectionCard, { FieldGrid } from './section_card'
import type { ModelFile, Preset, SchemaArg } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useCatalog } from '@/hooks/useCatalog'
import useMenuBar from '@/hooks/useMenubar'
import { useI18n } from '@/i18n'
import { SparklesIcon } from 'lucide-react'

type CatalogStatusProps = { catalogId: string | null }

/** Whether the download-catalog bundle behind a model file is on disk. */
const CatalogStatus = ({ catalogId }: CatalogStatusProps) => {
    const { t } = useI18n()
    const go = useMenuBar((state) => state.go)
    const catalog = useCatalog()
    const entry = catalogId ? catalog.data?.find((item) => item.id === catalogId) : undefined

    if (!catalogId || !entry) return null

    const present = entry.files.filter((file) => file.present).length
    if (present === entry.files.length) {
        return (
            <Badge variant="cyan" title={entry.name}>
                {t('model.installed')}
            </Badge>
        )
    }

    return (
        <>
            <Badge variant="muted" title={entry.name}>
                {t('model.missing', { present, total: entry.files.length })}
            </Badge>
            <Button variant="link" onClick={() => go('downloads')}>
                {t('model.openDownloads', { name: entry.name })}
            </Button>
        </>
    )
}

type ModelFilesSectionProps = {
    preset: Preset
    args: Map<string, SchemaArg>
    values: Record<string, FieldValue>
    initial: Record<string, FieldValue>
    schemaDefaults: Record<string, FieldValue>
    modelDests: ReadonlySet<string>
    onChange: (dest: string, value: FieldValue) => void
}

const ModelFilesSection = ({
    preset,
    args,
    values,
    initial,
    schemaDefaults,
    modelDests,
    onChange
}: ModelFilesSectionProps) => {
    const { t } = useI18n()

    const renderFile = (file: ModelFile) => {
        const arg = args.get(file.dest)
        if (!arg) return null
        const value = values[file.dest]

        return (
            <SchemaField
                key={file.dest}
                arg={arg}
                value={value ?? ''}
                resetValue={initial[file.dest] ?? ''}
                schemaDefault={schemaDefaults[file.dest] ?? ''}
                pathKind={pathKindFor(arg, modelDests)}
                required={file.required}
                onChange={onChange}
                footer={
                    file.suggested || file.catalog_id ? (
                        <div className="flex flex-wrap items-center gap-2">
                            {file.suggested ? (
                                <Button
                                    variant="outline"
                                    title={file.suggested}
                                    disabled={value === file.suggested}
                                    onClick={() => onChange(file.dest, file.suggested ?? '')}
                                >
                                    <SparklesIcon />
                                    {t('model.useSuggested')}
                                </Button>
                            ) : null}
                            <CatalogStatus catalogId={file.catalog_id} />
                        </div>
                    ) : null
                }
            />
        )
    }

    if (preset.model_files.length === 0) return null

    return (
        <SectionCard title={t('section.modelFiles')} description={t('section.modelFiles.desc')}>
            <FieldGrid>{preset.model_files.map(renderFile)}</FieldGrid>
        </SectionCard>
    )
}

export default ModelFilesSection
