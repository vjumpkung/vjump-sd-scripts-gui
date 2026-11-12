import { apiClient, apiUrl } from './client'
import type {
    CatalogEntry,
    DatasetConfig,
    DatasetInput,
    DatasetSummary,
    DownloadJob,
    FsListing,
    ImageFile,
    ImageFolder,
    JobRequest,
    PresetsResponse,
    PreviewResponse,
    QueueStatus,
    ScriptSchema,
    SecretsUpdate,
    SystemResourceSnapshot,
    SystemStatus,
    TrainingArtifacts,
    TrainingJob,
    TrainingLogChunk,
    ValidateReport
} from './types'

export const queryKeys = {
    status: ['system', 'status'] as const,
    resources: ['system', 'resources'] as const,
    presets: ['presets'] as const,
    schema: (script: string) => ['schema', script] as const,
    datasets: ['datasets'] as const,
    dataset: (id: string) => ['datasets', id] as const,
    folders: ['datasets', 'folders'] as const,
    folderFiles: (folder: string) => ['datasets', 'folders', folder, 'files'] as const,
    catalog: ['downloads', 'catalog'] as const,
    downloads: ['downloads', 'jobs'] as const,
    queue: ['training', 'queue'] as const,
    jobs: ['training', 'jobs'] as const,
    job: (jobId: string) => ['training', 'jobs', jobId] as const,
    artifacts: (jobId: string) => ['training', 'artifacts', jobId] as const,
    fs: (path: string, ext: string) => ['fs', path, ext] as const
}

export const mutationKeys = {
    // Shared by every dataset upload so navigation can be guarded while one is running.
    managedUpload: ['datasets', 'upload'] as const
}

const enc = encodeURIComponent

export const systemApi = {
    status: async () => (await apiClient.get<SystemStatus>('/api/system/status')).data,
    resources: async () =>
        (await apiClient.get<SystemResourceSnapshot>('/api/system/resources')).data,
    rescan: async () => (await apiClient.post<SystemStatus>('/api/system/rescan')).data,
    saveSecrets: async (body: SecretsUpdate) => {
        await apiClient.put('/api/system/secrets', body)
    }
}

export const presetsApi = {
    list: async () => (await apiClient.get<PresetsResponse>('/api/presets')).data,
    schema: async (script: string) =>
        (await apiClient.get<ScriptSchema>(`/api/schema/${enc(script)}`)).data
}

export const fsApi = {
    list: async (path: string, ext?: string) =>
        (
            await apiClient.get<FsListing>('/api/fs/list', {
                params: { ...(path ? { path } : {}), ...(ext ? { ext } : {}) }
            })
        ).data
}

export type UploadProgressHandler = (loaded: number, total: number) => void

export const datasetsApi = {
    list: async () => (await apiClient.get<DatasetSummary[]>('/api/datasets')).data,
    get: async (id: string) =>
        (await apiClient.get<DatasetConfig>(`/api/datasets/${enc(id)}`)).data,
    create: async (body: DatasetInput) =>
        (await apiClient.post<DatasetConfig>('/api/datasets', body)).data,
    update: async (id: string, body: DatasetInput) =>
        (await apiClient.put<DatasetConfig>(`/api/datasets/${enc(id)}`, body)).data,
    remove: async (id: string) => {
        await apiClient.delete(`/api/datasets/${enc(id)}`)
    },
    import: async (file: File, name?: string) => {
        const form = new FormData()
        form.append('file', file)
        if (name) form.append('name', name)
        return (await apiClient.post<DatasetConfig>('/api/datasets/import', form)).data
    },
    exportUrl: (id: string) => apiUrl(`/api/datasets/${enc(id)}/export`),
    validate: async (id: string) =>
        (await apiClient.post<ValidateReport>(`/api/datasets/${enc(id)}/validate`)).data,

    folders: async () => (await apiClient.get<ImageFolder[]>('/api/datasets/folders')).data,
    createFolder: async (name: string) =>
        (await apiClient.post<ImageFolder>('/api/datasets/folders', { name })).data,
    deleteFolder: async (folder: string) => {
        await apiClient.delete(`/api/datasets/folders/${enc(folder)}`)
    },
    folderFiles: async (folder: string) =>
        (await apiClient.get<{ files: ImageFile[] }>(`/api/datasets/folders/${enc(folder)}/files`))
            .data.files,
    uploadFile: async (
        folder: string,
        file: File,
        caption: string | null,
        options: { signal?: AbortSignal; onProgress?: UploadProgressHandler } = {}
    ) => {
        const form = new FormData()
        form.append('file', file, file.name)
        if (caption !== null) form.append('caption', caption)
        return (
            await apiClient.put<ImageFile>(`/api/datasets/folders/${enc(folder)}/files`, form, {
                timeout: 0,
                signal: options.signal,
                onUploadProgress: (event) =>
                    options.onProgress?.(event.loaded, event.total ?? file.size)
            })
        ).data
    },
    fileUrl: (folder: string, name: string) =>
        apiUrl(`/api/datasets/folders/${enc(folder)}/files/${enc(name)}`),
    deleteFile: async (folder: string, name: string) => {
        await apiClient.delete(`/api/datasets/folders/${enc(folder)}/files/${enc(name)}`)
    },
    saveCaption: async (folder: string, stem: string, caption: string) =>
        (
            await apiClient.put<{ name: string; caption: string }>(
                `/api/datasets/folders/${enc(folder)}/captions/${enc(stem)}`,
                { caption }
            )
        ).data
}

export const downloadsApi = {
    catalog: async () => (await apiClient.get<CatalogEntry[]>('/api/downloads/catalog')).data,
    list: async () => (await apiClient.get<DownloadJob[]>('/api/downloads')).data,
    start: async (modelId: string) =>
        (await apiClient.post<DownloadJob>('/api/downloads', { model_id: modelId })).data,
    cancel: async (jobId: string) =>
        (await apiClient.post<DownloadJob>(`/api/downloads/${enc(jobId)}/cancel`)).data
}

export const trainingApi = {
    preview: async (request: JobRequest) =>
        (await apiClient.post<PreviewResponse>('/api/training/preview', request)).data,
    createJob: async (request: JobRequest) =>
        (await apiClient.post<TrainingJob>('/api/training/jobs', request)).data,
    getQueue: async () => (await apiClient.get<QueueStatus>('/api/training/queue')).data,
    startQueue: async () => (await apiClient.post<QueueStatus>('/api/training/queue/start')).data,
    pauseQueue: async () => (await apiClient.post<QueueStatus>('/api/training/queue/pause')).data,
    listJobs: async () => (await apiClient.get<TrainingJob[]>('/api/training/jobs')).data,
    getLogs: async (jobId: string, offset: number) =>
        (
            await apiClient.get<TrainingLogChunk>(`/api/training/jobs/${enc(jobId)}/logs`, {
                params: { offset }
            })
        ).data,
    getArtifacts: async (jobId: string) =>
        (await apiClient.get<TrainingArtifacts>(`/api/training/jobs/${enc(jobId)}/artifacts`)).data,
    artifactUrl: (jobId: string, name: string) =>
        apiUrl(`/api/training/jobs/${enc(jobId)}/artifacts/${enc(name)}/download`),
    artifactsZipUrl: (jobId: string) =>
        apiUrl(`/api/training/jobs/${enc(jobId)}/artifacts/download`),
    configUrl: (jobId: string) => apiUrl(`/api/training/jobs/${enc(jobId)}/config/download`),
    cancel: async (jobId: string) =>
        (await apiClient.post<TrainingJob>(`/api/training/jobs/${enc(jobId)}/cancel`)).data,
    retry: async (jobId: string) =>
        (await apiClient.post<TrainingJob>(`/api/training/jobs/${enc(jobId)}/retry`)).data,
    reorder: async (jobId: string, queuePosition: number) =>
        (
            await apiClient.patch<TrainingJob>(`/api/training/jobs/${enc(jobId)}`, {
                queue_position: queuePosition
            })
        ).data,
    remove: async (jobId: string) => {
        await apiClient.delete(`/api/training/jobs/${enc(jobId)}`)
    }
}
