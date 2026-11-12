import { queryKeys, systemApi } from '@/api/api'
import { getApiErrorMessage } from '@/api/client'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { useI18n } from '@/i18n'
import { clampPercent, formatBytes, formatPercent, formatTime } from '@/lib/format'
import { useQuery } from '@tanstack/react-query'
import { CpuIcon, GpuIcon, MemoryStickIcon, RefreshCwIcon } from 'lucide-react'
import { type ReactNode } from 'react'

const MONITOR_INTERVAL_MS = 5_000

type ResourceMeterProps = {
    label: string
    icon: ReactNode
    percent: number | null
    detail: string
    note: string
}

const ResourceMeter = ({ label, icon, percent, detail, note }: ResourceMeterProps) => {
    const { t, tag } = useI18n()

    return (
        <div className="rounded-lg border border-border p-4">
            <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                    <span className="text-muted-foreground [&>svg]:size-5">{icon}</span>
                    <p className="truncate text-sm font-semibold" title={label}>
                        {label}
                    </p>
                </div>
                <span className="tabular text-2xl font-bold tracking-tight">
                    {formatPercent(percent, tag, 1)}
                </span>
            </div>
            <Progress
                value={percent === null ? null : clampPercent(percent)}
                className="mt-4"
                aria-label={`${label} ${t('monitor.utilization')}`}
            />
            <div className="tabular mt-3 flex items-end justify-between gap-3 text-xs">
                <span className="font-medium">{detail}</span>
                <span className="text-right text-muted-foreground">{note}</span>
            </div>
        </div>
    )
}

const SystemMonitor = () => {
    const { t, tag } = useI18n()
    const resourcesQuery = useQuery({
        queryKey: queryKeys.resources,
        queryFn: systemApi.resources,
        refetchInterval: MONITOR_INTERVAL_MS,
        refetchOnWindowFocus: false
    })
    const resources = resourcesQuery.data
    const updatedAt = resources ? new Date(resources.timestamp) : null

    return (
        <Card className="mb-6">
            <CardHeader className="mb-4 gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                    <CardTitle>{t('monitor.title')}</CardTitle>
                    <CardDescription>{t('monitor.subtitle')}</CardDescription>
                </div>
                <div className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                    <RefreshCwIcon
                        aria-hidden
                        className={`size-4 ${resourcesQuery.isFetching ? 'motion-safe:animate-spin' : ''}`}
                    />
                    {updatedAt && !Number.isNaN(updatedAt.getTime())
                        ? t('monitor.updated', { time: formatTime(updatedAt, tag) })
                        : t('monitor.every')}
                </div>
            </CardHeader>

            {resourcesQuery.error ? (
                <p role="alert" className="text-sm text-destructive">
                    {getApiErrorMessage(resourcesQuery.error, t('monitor.error'))}
                </p>
            ) : resources ? (
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <ResourceMeter
                        label="CPU"
                        icon={<CpuIcon />}
                        percent={resources.cpu.percent}
                        detail={t('monitor.logical', { count: resources.cpu.logical_cores ?? '-' })}
                        note={t('monitor.physical', { count: resources.cpu.physical_cores ?? '-' })}
                    />
                    <ResourceMeter
                        label="RAM"
                        icon={<MemoryStickIcon />}
                        percent={resources.ram.percent}
                        detail={t('monitor.used', {
                            value: formatBytes(resources.ram.used_bytes, tag)
                        })}
                        note={t('monitor.total', {
                            value: formatBytes(resources.ram.total_bytes, tag)
                        })}
                    />
                    {resources.gpus.flatMap((gpu) => [
                        <ResourceMeter
                            key={`gpu-${gpu.index}`}
                            label={`GPU ${gpu.index} · ${gpu.name}`}
                            icon={<GpuIcon />}
                            percent={gpu.utilization_percent}
                            detail={
                                gpu.temperature_c === null
                                    ? t('monitor.tempUnavailable')
                                    : `${Math.round(gpu.temperature_c)} °C`
                            }
                            note={t('monitor.compute')}
                        />,
                        <ResourceMeter
                            key={`vram-${gpu.index}`}
                            label={`VRAM ${gpu.index}`}
                            icon={<MemoryStickIcon />}
                            percent={
                                gpu.memory_used_bytes !== null && gpu.memory_total_bytes
                                    ? (gpu.memory_used_bytes / gpu.memory_total_bytes) * 100
                                    : null
                            }
                            detail={t('monitor.used', {
                                value: formatBytes(gpu.memory_used_bytes, tag)
                            })}
                            note={t('monitor.total', {
                                value: formatBytes(gpu.memory_total_bytes, tag)
                            })}
                        />
                    ])}
                    {resources.gpus.length === 0 ? (
                        <div className="rounded-lg border border-dashed border-border p-4 sm:col-span-2">
                            <div className="flex items-center gap-2 text-sm font-semibold">
                                <GpuIcon className="size-5 text-muted-foreground" />
                                {t('monitor.noGpu')}
                            </div>
                            <p className="mt-2 text-xs leading-5 text-muted-foreground">
                                {resources.gpu_error ?? t('monitor.noGpuBody')}
                            </p>
                        </div>
                    ) : null}
                </div>
            ) : (
                <p className="rounded-lg bg-muted p-4 text-sm text-muted-foreground">
                    {t('monitor.loading')}
                </p>
            )}
        </Card>
    )
}

export default SystemMonitor
