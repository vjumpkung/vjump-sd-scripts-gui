import AllParameters from './all_parameters'
import EssentialSections from './essential_sections'
import {
    type FieldValue,
    type FormValues,
    applyOverrides,
    argMap,
    buildConfigFile,
    buildInitialValues,
    buildJobRequest,
    buildSchemaDefaults,
    diffOverrides,
    isEmptyValue,
    isExcludedFromValues,
    readDraft,
    requiredDests,
    slugify,
    validateValue,
    writeDraft
} from './form_state'
import ModelFilesSection from './model_files_section'
import ProjectSection from './project_section'
import TrainingAside, { type ImportStatus, type ReadinessItem } from './training_aside'
import { datasetsApi, queryKeys } from '@/api/api'
import type { Preset, ScriptSchema } from '@/api/types'
import useAccelerationSettings, { toAccelerateRequest } from '@/hooks/useAccelerationSettings'
import { useI18n } from '@/i18n'
import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

type PresetEditorProps = {
    preset: Preset
    schema: ScriptSchema
    importStatus: ImportStatus | null
    onImportFile: (file: File) => void
}

/**
 * The whole form for one preset. It owns the values, restores them from the preset's draft when
 * it mounts, and writes the draft back as the user edits (docs: drafts live in localStorage).
 */
const PresetEditor = ({ preset, schema, importStatus, onImportFile }: PresetEditorProps) => {
    const { t, lookup } = useI18n()
    const accelerate = useAccelerationSettings((state) => state.settings)
    const accelerateRequest = useMemo(() => toAccelerateRequest(accelerate), [accelerate])

    const args = useMemo(() => argMap(schema), [schema])
    const required = useMemo(() => requiredDests(preset, schema), [preset, schema])
    const initial = useMemo(() => buildInitialValues(preset, schema), [preset, schema])
    const schemaDefaults = useMemo(() => buildSchemaDefaults(schema), [schema])
    const modelDests = useMemo(
        () => new Set(preset.model_files.map((file) => file.dest)),
        [preset.model_files]
    )

    const [draft] = useState(() => readDraft(preset.id))
    const [values, setValues] = useState<FormValues>(() =>
        applyOverrides(initial, draft.overrides, schema)
    )
    const [name, setName] = useState(draft.name)
    const [outputNameEdited, setOutputNameEdited] = useState(draft.outputNameEdited)
    const [datasetConfigId, setDatasetConfigId] = useState(draft.datasetConfigId)
    const [inlineFiles, setInlineFiles] = useState<Record<string, string>>(draft.inlineFiles)

    const datasetsQuery = useQuery({ queryKey: queryKeys.datasets, queryFn: datasetsApi.list })
    const datasets = useMemo(() => datasetsQuery.data ?? [], [datasetsQuery.data])
    const needsDataset = preset.dataset_kinds.length > 0
    const effectiveDatasetId =
        needsDataset &&
        datasets.some(
            (dataset) =>
                dataset.id === datasetConfigId &&
                dataset.kinds.every((kind) => preset.dataset_kinds.includes(kind))
        )
            ? datasetConfigId
            : ''

    // ---- draft persistence ----
    const latest = useRef({ name, outputNameEdited, datasetConfigId, values, inlineFiles })
    latest.current = { name, outputNameEdited, datasetConfigId, values, inlineFiles }

    const persist = useCallback(() => {
        const state = latest.current
        writeDraft(preset.id, {
            version: 1,
            name: state.name,
            outputNameEdited: state.outputNameEdited,
            datasetConfigId: state.datasetConfigId,
            overrides: diffOverrides(state.values, initial, schema),
            inlineFiles: state.inlineFiles
        })
    }, [preset.id, initial, schema])

    useEffect(() => {
        const timer = window.setTimeout(persist, 300)
        return () => window.clearTimeout(timer)
    }, [persist, name, outputNameEdited, datasetConfigId, values, inlineFiles])

    // Flush on unmount so switching presets never loses the last keystrokes.
    useEffect(() => persist, [persist])

    // ---- edits ----
    const handleChange = useCallback((dest: string, value: FieldValue) => {
        setValues((current) => (current[dest] === value ? current : { ...current, [dest]: value }))
        if (dest === 'output_name') {
            setOutputNameEdited(typeof value === 'string' && value.trim() !== '')
        }
    }, [])

    const handleNameChange = (next: string) => {
        setName(next)
        if (!outputNameEdited) {
            setValues((current) => ({ ...current, output_name: slugify(next) }))
        }
    }

    const handleInlineChange = useCallback((dest: string, text: string) => {
        setInlineFiles((current) => ({ ...current, [dest]: text }))
    }, [])

    const restoreDefaults = () => {
        setValues({ ...initial, ...(name.trim() ? { output_name: slugify(name) } : {}) })
        setInlineFiles({})
        setOutputNameEdited(false)
    }

    // ---- readiness and request ----
    const fieldLabel = (dest: string) => lookup(`fields.${dest}.label`) ?? dest
    const isFilled = (dest: string) =>
        dest in preset.inline_files
            ? (inlineFiles[dest] ?? '').trim() !== ''
            : !isEmptyValue(values[dest])

    const invalidCount = useMemo(
        () =>
            schema.args.filter(
                (arg) =>
                    !isExcludedFromValues(preset, arg.dest) &&
                    validateValue(arg, values[arg.dest]) !== null
            ).length,
        [preset, schema, values]
    )

    const readiness: ReadinessItem[] = [
        { id: '__name', label: t('ready.name'), ok: name.trim() !== '' },
        ...(needsDataset
            ? [{ id: '__dataset', label: t('ready.dataset'), ok: effectiveDatasetId !== '' }]
            : []),
        ...required.map((dest) => ({
            id: dest,
            label: fieldLabel(dest),
            ok: isFilled(dest)
        })),
        { id: '__valid', label: t('ready.valid'), ok: invalidCount === 0 }
    ]
    const ready = readiness.every((item) => item.ok)

    const request = useMemo(
        () =>
            buildJobRequest(
                preset,
                schema,
                schemaDefaults,
                { name, datasetConfigId: effectiveDatasetId, values, inlineFiles },
                accelerateRequest
            ),
        [
            preset,
            schema,
            schemaDefaults,
            name,
            effectiveDatasetId,
            values,
            inlineFiles,
            accelerateRequest
        ]
    )

    const exportConfig = () => {
        const blob = new Blob([JSON.stringify(buildConfigFile(request), null, 4)], {
            type: 'application/json'
        })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `${preset.id}-training-config.json`
        link.click()
        window.setTimeout(() => URL.revokeObjectURL(url), 0)
    }

    const acceleratePreview = t('aside.accelerate', {
        processes: accelerateRequest.num_processes,
        machines: accelerateRequest.num_machines,
        threads: accelerateRequest.num_cpu_threads_per_process,
        dynamo: accelerateRequest.dynamo_backend
    })

    return (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem] xl:items-start">
            <div className="flex min-w-0 flex-col gap-6">
                <ProjectSection
                    preset={preset}
                    required={required}
                    args={args}
                    name={name}
                    onNameChange={handleNameChange}
                    values={values}
                    initial={initial}
                    schemaDefaults={schemaDefaults}
                    onChange={handleChange}
                    datasets={datasets}
                    datasetsLoading={datasetsQuery.isPending}
                    datasetConfigId={effectiveDatasetId}
                    onDatasetChange={setDatasetConfigId}
                />
                <ModelFilesSection
                    preset={preset}
                    args={args}
                    values={values}
                    initial={initial}
                    schemaDefaults={schemaDefaults}
                    modelDests={modelDests}
                    onChange={handleChange}
                />
                <EssentialSections
                    preset={preset}
                    required={required}
                    args={args}
                    values={values}
                    initial={initial}
                    schemaDefaults={schemaDefaults}
                    modelDests={modelDests}
                    onChange={handleChange}
                    inlineFiles={inlineFiles}
                    onInlineChange={handleInlineChange}
                />
                <AllParameters
                    preset={preset}
                    required={required}
                    schema={schema}
                    values={values}
                    initial={initial}
                    schemaDefaults={schemaDefaults}
                    modelDests={modelDests}
                    onChange={handleChange}
                />
            </div>
            <TrainingAside
                preset={preset}
                request={request}
                readiness={readiness}
                ready={ready}
                acceleratePreview={acceleratePreview}
                importStatus={importStatus}
                onExport={exportConfig}
                onImportFile={onImportFile}
                onRestoreDefaults={restoreDefaults}
            />
        </div>
    )
}

export default PresetEditor
