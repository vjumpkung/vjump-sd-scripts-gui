/* Types for the backend contract. Source of truth: docs/api.md */

// ---- 1. System -------------------------------------------------------------------------------

export type RescanState = 'idle' | 'running' | 'failed'

export type SystemStatus = {
    version: string
    desktop: boolean
    auth: boolean
    workspace_root: string
    sd_scripts: {
        dir: string
        python: string
        python_ok: boolean
        commit: string | null
    }
    schema: {
        source: 'generated' | 'bundled'
        commit: string | null
        stale: boolean
        rescan: { state: RescanState; error: string | null }
    }
    secrets: { hf_token: boolean; wandb_api_key: boolean }
}

export type GpuResourceUsage = {
    index: number
    name: string
    utilization_percent: number | null
    memory_used_bytes: number | null
    memory_total_bytes: number | null
    temperature_c: number | null
}

export type SystemResourceSnapshot = {
    timestamp: string
    cpu: { percent: number; logical_cores: number | null; physical_cores: number | null }
    ram: { percent: number; used_bytes: number; available_bytes: number; total_bytes: number }
    gpus: GpuResourceUsage[]
    gpu_error: string | null
}

export type SecretsUpdate = { hf_token?: string | null; wandb_api_key?: string | null }

// ---- 2. Presets and schema ------------------------------------------------------------------

export type ModelFile = {
    dest: string
    required: boolean
    suggested: string | null
    catalog_id: string | null
}

export type EssentialsSection = { id: string; dests: string[] }

export type DatasetKind = 'dreambooth' | 'finetune' | 'controlnet'

export type Preset = {
    id: string
    family: string
    type: string
    script: string
    dataset_kinds: DatasetKind[]
    network_modules: string[] | null
    model_files: ModelFile[]
    required: string[]
    defaults: Record<string, unknown>
    essentials: EssentialsSection[]
    inline_files: Record<string, string>
    notes: string[]
}

export type PresetsResponse = { families: string[]; presets: Preset[] }

export type ArgKind = 'bool' | 'int' | 'float' | 'int_or_float' | 'str' | 'list'
export type ItemKind = 'int' | 'float' | 'str'

export type SchemaArg = {
    dest: string
    flag: string
    kind: ArgKind
    item_kind: ItemKind | null
    min: number | null
    required: boolean
    default: unknown
    choices: Array<string | number> | null
    help_en: string | null
    help_ja: string | null
    group: string
}

export type ScriptSchema = {
    script: string
    commit: string | null
    source: string
    args: SchemaArg[]
}

// ---- 3. File browser ------------------------------------------------------------------------

export type FsEntry = {
    name: string
    kind: 'file' | 'dir'
    size_bytes: number | null
    abs_path: string
}

export type FsListing = { root: string; path: string; entries: FsEntry[] }

// ---- 4. Datasets ----------------------------------------------------------------------------

export type DatasetConfigBody = {
    general?: Record<string, unknown>
    datasets: Array<Record<string, unknown>>
}

export type DatasetSummary = {
    id: string
    name: string
    description: string
    kinds: DatasetKind[]
    created_at: string
    updated_at: string
}

export type DatasetConfig = DatasetSummary & {
    config: DatasetConfigBody
    warnings: string[]
}

export type DatasetInput = { name: string; description?: string; config: DatasetConfigBody }

export type ValidateSubset = {
    index: number
    kind: DatasetKind
    path: string
    exists: boolean
    images: number
    captions: number
    missing_captions: string[]
}

export type ValidateReport = {
    ok: boolean
    datasets: Array<{ index: number; subsets: ValidateSubset[] }>
}

export type ImageFolder = {
    name: string
    path: string
    abs_path: string
    images: number
    captions: number
    size_bytes: number
}

export type ImageFile = { name: string; size_bytes: number; caption: string | null }

// ---- 5. Downloads ---------------------------------------------------------------------------

export type CatalogFile = { path: string; size_bytes: number; present: boolean }

export type CatalogEntry = {
    id: string
    name: string
    family: string
    gated: boolean
    size_bytes: number
    files: CatalogFile[]
}

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

export type DownloadJob = {
    id: string
    model_id: string
    status: JobStatus
    progress: number
    current_file: string | null
    downloaded_bytes: number
    total_bytes: number
    error: string | null
    created_at: string
}

// ---- 6. Training ----------------------------------------------------------------------------

export type AccelerateRequest = {
    num_processes: number
    num_machines: number
    num_cpu_threads_per_process: number
    dynamo_backend: string
}

export type JobRequest = {
    name: string
    preset_id: string
    dataset_config_id: string | null
    values: Record<string, unknown>
    inline_files: Record<string, string>
    accelerate: AccelerateRequest
}

export type PreviewResponse = {
    command: string
    argv: string[]
    dataset_toml: string | null
    errors: string[]
}

export type TrainingProgress = {
    epoch: number | null
    total_epochs: number | null
    step: number | null
    total_steps: number | null
    percent: number | null
}

export type TrainingJob = {
    id: string
    name: string
    preset_id: string
    script: string
    dataset_config_id: string | null
    status: JobStatus
    queue_position: number | null
    progress: TrainingProgress | null
    error: string | null
    output_dir: string
    output_name: string
    created_at: string
    started_at: string | null
    finished_at: string | null
}

export type QueueStatus = {
    state: 'paused' | 'running'
    queued: number
    running_job_id: string | null
}

export type TrainingLogChunk = {
    offset: number
    next_offset: number
    content: string
    eof: boolean
}

export type TrainingArtifact = {
    name: string
    size_bytes: number
    kind: 'final' | 'epoch' | 'step'
}

export type TrainingArtifacts = { files: TrainingArtifact[]; total_size_bytes: number }

export const TRAINING_CONFIG_SCHEMA = 'sd-scripts-gui.training-config'

export type TrainingConfigFile = {
    schema: typeof TRAINING_CONFIG_SCHEMA
    version: 1
    preset_id: string
    name: string
    values: Record<string, unknown>
    inline_files: Record<string, string>
    accelerate: AccelerateRequest
}
