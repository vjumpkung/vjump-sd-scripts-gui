import type { AccelerateRequest } from '../api/types'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// Inputs are kept as strings so the user can clear a field while typing.
export type AccelerationSettings = {
    numProcesses: string
    numMachines: string
    numCpuThreadsPerProcess: string
    dynamoBackend: string
}

export const dynamoBackends = ['no', 'eager', 'aot_eager', 'inductor'] as const

export const defaultAccelerationSettings: AccelerationSettings = {
    numProcesses: '1',
    numMachines: '1',
    numCpuThreadsPerProcess: '1',
    dynamoBackend: 'no'
}

const positiveInt = (value: string, fallback: number) => {
    const parsed = Number.parseInt(value, 10)
    return Number.isFinite(parsed) && parsed >= 1 ? parsed : fallback
}

export const isValidAccelerationSettings = (settings: AccelerationSettings) =>
    [settings.numProcesses, settings.numMachines, settings.numCpuThreadsPerProcess].every((value) =>
        /^[1-9]\d*$/.test(value.trim())
    )

export const toAccelerateRequest = (settings: AccelerationSettings): AccelerateRequest => ({
    num_processes: positiveInt(settings.numProcesses, 1),
    num_machines: positiveInt(settings.numMachines, 1),
    num_cpu_threads_per_process: positiveInt(settings.numCpuThreadsPerProcess, 1),
    dynamo_backend: (dynamoBackends as readonly string[]).includes(settings.dynamoBackend)
        ? settings.dynamoBackend
        : 'no'
})

export const fromAccelerateRequest = (request: AccelerateRequest): AccelerationSettings => ({
    numProcesses: String(request.num_processes),
    numMachines: String(request.num_machines),
    numCpuThreadsPerProcess: String(request.num_cpu_threads_per_process),
    dynamoBackend: request.dynamo_backend
})

type AccelerationSettingsState = {
    settings: AccelerationSettings
    setSetting: (key: keyof AccelerationSettings, value: string) => void
    setSettings: (settings: AccelerationSettings) => void
    resetSettings: () => void
}

const useAccelerationSettings = create<AccelerationSettingsState>()(
    persist(
        (set) => ({
            settings: { ...defaultAccelerationSettings },
            setSetting: (key, value) =>
                set((state) => ({ settings: { ...state.settings, [key]: value } })),
            setSettings: (settings) => set({ settings }),
            resetSettings: () => set({ settings: { ...defaultAccelerationSettings } })
        }),
        {
            name: 'sdgui:accelerate',
            version: 1
        }
    )
)

export default useAccelerationSettings
