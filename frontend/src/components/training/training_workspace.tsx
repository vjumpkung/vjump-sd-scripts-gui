import {
    buildInitialValues,
    buildSchemaDefaults,
    diffOverrides,
    importedOverrides,
    parseConfigFile,
    readDraft,
    writeDraft
} from './form_state'
import PresetEditor from './preset_editor'
import type { ImportStatus } from './training_aside'
import { presetsApi, queryKeys } from '@/api/api'
import { getApiErrorMessage, httpStatus } from '@/api/client'
import PageHeader from '@/components/page_header'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import useAccelerationSettings, { fromAccelerateRequest } from '@/hooks/useAccelerationSettings'
import useMenuBar from '@/hooks/useMenubar'
import { usePresets, useSystemStatus } from '@/hooks/useSystem'
import { useI18n } from '@/i18n'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { RefreshCwIcon } from 'lucide-react'
import { useState } from 'react'

const SELECTION_KEY = 'sdgui:preset-selection'

const readSelection = (): Record<string, string> => {
    try {
        const parsed: unknown = JSON.parse(window.localStorage.getItem(SELECTION_KEY) ?? '{}')
        return typeof parsed === 'object' && parsed !== null
            ? (parsed as Record<string, string>)
            : {}
    } catch {
        return {}
    }
}

const SchemaSkeleton = () => (
    <div className="flex flex-col gap-6" aria-busy="true">
        {[0, 1, 2].map((index) => (
            <div
                key={index}
                className="h-48 rounded-xl border border-border bg-card motion-safe:animate-pulse"
            />
        ))}
    </div>
)

const TrainingWorkspace = () => {
    const { t, lookup } = useI18n()
    const queryClient = useQueryClient()
    const presetsQuery = usePresets()
    const status = useSystemStatus()
    const familyFromStore = useMenuBar((state) => state.family)
    const go = useMenuBar((state) => state.go)
    const setAcceleration = useAccelerationSettings((state) => state.setSettings)
    const [selection, setSelection] = useState(readSelection)
    const [reloadKey, setReloadKey] = useState(0)
    const [importStatus, setImportStatus] = useState<ImportStatus | null>(null)

    const families = presetsQuery.data?.families ?? []
    const allPresets = presetsQuery.data?.presets ?? []
    const family =
        familyFromStore && families.includes(familyFromStore) ? familyFromStore : families[0]
    const presets = allPresets.filter((preset) => preset.family === family)
    const preset = presets.find((item) => item.id === selection[family ?? '']) ?? presets[0]

    const schemaQuery = useQuery({
        queryKey: queryKeys.schema(preset?.script ?? ''),
        queryFn: () => presetsApi.schema(preset?.script ?? ''),
        enabled: Boolean(preset),
        staleTime: 5 * 60_000,
        retry: 1
    })

    const presetName = (id: string) => lookup(`presets.${id}.name`) ?? lookup(`types.${id}`) ?? id
    const presetLabel = (id: string, type: string, familyId: string) =>
        lookup(`presets.${id}.name`) ??
        `${lookup(`family.${familyId}`) ?? familyId} ${lookup(`types.${type}`) ?? type}`

    const selectPreset = (familyId: string, id: string) => {
        setSelection((current) => {
            const next = { ...current, [familyId]: id }
            try {
                window.localStorage.setItem(SELECTION_KEY, JSON.stringify(next))
            } catch {
                // Remembering the tab is a convenience only.
            }
            return next
        })
    }

    const importConfig = async (file: File) => {
        try {
            if (file.size > 1_000_000) {
                setImportStatus({ kind: 'error', message: t('import.error.size') })
                return
            }
            const parsed: unknown = JSON.parse(await file.text())
            const result = parseConfigFile(
                parsed,
                allPresets.map((item) => item.id)
            )
            if (!result.ok) {
                setImportStatus({ kind: 'error', message: t(`import.error.${result.error}`) })
                return
            }

            const { config } = result
            const target = allPresets.find((item) => item.id === config.presetId)
            if (!target) return
            const schema = await queryClient.fetchQuery({
                queryKey: queryKeys.schema(target.script),
                queryFn: () => presetsApi.schema(target.script),
                staleTime: 5 * 60_000
            })

            // Fields the file leaves out are at the sd-scripts default, not at the preset default.
            const initial = buildInitialValues(target, schema)
            const full = {
                ...buildSchemaDefaults(schema),
                ...importedOverrides(config.values, schema)
            }
            const existing = readDraft(target.id)
            writeDraft(target.id, {
                version: 1,
                name: config.name || existing.name,
                outputNameEdited: 'output_name' in config.values,
                datasetConfigId: existing.datasetConfigId,
                overrides: diffOverrides(full, initial, schema),
                inlineFiles: config.inlineFiles
            })
            if (config.accelerate) setAcceleration(fromAccelerateRequest(config.accelerate))

            selectPreset(target.family, target.id)
            go('training', target.family)
            setReloadKey((key) => key + 1)
            setImportStatus({
                kind: 'ok',
                message: t('import.ok', { name: presetName(target.id) })
            })
        } catch (error) {
            setImportStatus({
                kind: 'error',
                message: getApiErrorMessage(error, t('import.error.read'))
            })
        }
    }

    const familyName = family ? (lookup(`family.${family}`) ?? family) : ''
    const schemaUnavailable = httpStatus(schemaQuery.error) === 503

    return (
        <div>
            <PageHeader
                before={t('training.title.before')}
                mark={familyName || t('common.loading')}
                after={t('training.title.after')}
                description={t('training.subtitle')}
            />

            {status.data && !status.data.sd_scripts.python_ok ? (
                <Alert className="mb-6">
                    <AlertTitle>{t('env.notInstalled.title')}</AlertTitle>
                    <AlertDescription>{t('env.notInstalled.body')}</AlertDescription>
                </Alert>
            ) : null}

            {presetsQuery.isError ? (
                <Alert variant="destructive" className="mb-6">
                    <AlertTitle>{t('training.presetsError')}</AlertTitle>
                    <AlertDescription className="flex flex-col items-start gap-3">
                        {getApiErrorMessage(presetsQuery.error, t('training.presetsError'))}
                        <Button variant="outline" onClick={() => void presetsQuery.refetch()}>
                            <RefreshCwIcon />
                            {t('common.retry')}
                        </Button>
                    </AlertDescription>
                </Alert>
            ) : null}

            {presets.length > 0 && family ? (
                <div className="mb-6 flex flex-col gap-3">
                    <Tabs
                        value={preset?.id}
                        onValueChange={(id) => selectPreset(family, id)}
                        aria-label={t('training.presets')}
                    >
                        <TabsList aria-label={t('training.presets')}>
                            {presets.map((item) => (
                                <TabsTrigger key={item.id} value={item.id}>
                                    {presetLabel(item.id, item.type, item.family)}
                                </TabsTrigger>
                            ))}
                        </TabsList>
                    </Tabs>
                    {preset ? (
                        <p className="max-w-[44rem] text-[0.9375rem] leading-[1.65] text-muted-foreground">
                            {lookup(`presets.${preset.id}.desc`) ??
                                lookup(`types.${preset.type}.desc`) ??
                                ''}
                        </p>
                    ) : null}
                </div>
            ) : null}

            {presetsQuery.isPending ? <SchemaSkeleton /> : null}

            {preset ? (
                schemaQuery.data ? (
                    <PresetEditor
                        key={`${preset.id}:${reloadKey}`}
                        preset={preset}
                        schema={schemaQuery.data}
                        importStatus={importStatus}
                        onImportFile={(file) => void importConfig(file)}
                    />
                ) : schemaQuery.isError ? (
                    <Alert variant="destructive">
                        <AlertTitle>
                            {schemaUnavailable
                                ? t('training.schemaUnavailable')
                                : t('training.schemaError')}
                        </AlertTitle>
                        <AlertDescription className="flex flex-col items-start gap-3">
                            {getApiErrorMessage(schemaQuery.error, t('training.schemaError'))}
                            <div className="flex flex-wrap gap-2">
                                <Button
                                    variant="outline"
                                    onClick={() => void schemaQuery.refetch()}
                                >
                                    <RefreshCwIcon />
                                    {t('common.retry')}
                                </Button>
                                <Button variant="outline" onClick={() => go('settings')}>
                                    {t('training.openSettings')}
                                </Button>
                            </div>
                        </AlertDescription>
                    </Alert>
                ) : (
                    <SchemaSkeleton />
                )
            ) : null}
        </div>
    )
}

export default TrainingWorkspace
