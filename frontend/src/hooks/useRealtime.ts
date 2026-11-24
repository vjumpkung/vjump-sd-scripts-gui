import { queryKeys } from '@/api/api'
import {
    onInvalidate,
    onRealtimeConnect,
    onRealtimeDisconnect,
    realtimeSocket
} from '@/api/realtime'
import type {
    DownloadJob,
    DownloadProgressEvent,
    JobProgressEvent,
    RealtimeTopic,
    SystemResourceSnapshot,
    TrainingJob
} from '@/api/types'
import { type QueryClient, type QueryKey, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { create } from 'zustand'

type RealtimeState = {
    // True while the Socket.IO channel is up. Pollers fall back to their intervals when it is not.
    connected: boolean
}

export const useRealtimeConnected = create<RealtimeState>(() => ({ connected: false }))

// `training` lists the exact keys: the ['training'] prefix would also refetch the preview queries.
const TOPIC_KEYS: Record<RealtimeTopic, readonly QueryKey[]> = {
    training: [queryKeys.queue, queryKeys.jobs],
    downloads: [queryKeys.downloads],
    catalog: [queryKeys.catalog],
    status: [queryKeys.status],
    auth: [queryKeys.auth]
}

// Missed events are not replayed, so everything the channel feeds is re-read after a (re)connect.
const RESYNC_KEYS: readonly QueryKey[] = [
    queryKeys.queue,
    queryKeys.jobs,
    queryKeys.downloads,
    queryKeys.catalog,
    queryKeys.status,
    queryKeys.resources
]

const mergeProgress = <Row, Update>(
    client: QueryClient,
    queryKey: QueryKey,
    merge: (rows: Row[], updates: ReadonlyMap<string, Update>) => Row[]
) => {
    const cache = client.getQueryCache()
    const pending = new Map<string, Update>()
    let pendingQuery: object | undefined
    const apply = (updates: ReadonlyMap<string, Update>) => {
        client.setQueryData<Row[]>(queryKey, (rows) => rows && merge(rows, updates))
    }

    // Show pushes immediately and replay the latest per job if a concurrent REST read replaces
    // the list. Keep the replay scoped to that fetch so later reads can reconcile lifecycle state.
    const dispose = cache.subscribe(({ type, query }) => {
        if (query !== pendingQuery) return
        if (type === 'removed') {
            pending.clear()
            pendingQuery = undefined
        }
        if (type === 'updated' && query.state.fetchStatus === 'idle') {
            const updates = new Map(pending)
            pending.clear()
            pendingQuery = undefined
            apply(updates)
        }
    })

    return {
        push: (updates: ReadonlyMap<string, Update>) => {
            const query = cache.find({ queryKey })
            const state = query?.state
            if (state && state.fetchStatus !== 'idle') {
                pendingQuery = query
                for (const [id, update] of updates) pending.set(id, update)
            }
            if (state?.data !== undefined) apply(updates)
        },
        dispose
    }
}

/** Opens the realtime channel and synchronizes REST query caches. Mount once. */
export const useRealtimeSync = () => {
    const queryClient = useQueryClient()

    useEffect(() => {
        const jobs = mergeProgress<TrainingJob, JobProgressEvent['progress']>(
            queryClient,
            queryKeys.jobs,
            (rows, updates) =>
                rows.map((job) => {
                    const progress = updates.get(job.id)
                    return job.status === 'running' && progress ? { ...job, progress } : job
                })
        )
        const downloads = mergeProgress<DownloadJob, DownloadJob>(
            queryClient,
            queryKeys.downloads,
            (rows, updates) => {
                const byId = new Map(rows.map((job) => [job.id, job]))
                for (const [id, job] of updates) {
                    const current = byId.get(id)
                    // A delayed progress snapshot must not undo a terminal REST state.
                    if (current && current.status !== 'queued' && current.status !== 'running') {
                        continue
                    }
                    byId.set(id, job)
                }
                return [...byId.values()].sort((a, b) => b.created_at.localeCompare(a.created_at))
            }
        )
        const onJobProgress = ({ job_id, progress }: JobProgressEvent) => {
            jobs.push(new Map([[job_id, progress]]))
        }
        const onDownloadProgress = ({ jobs }: DownloadProgressEvent) => {
            downloads.push(new Map(jobs.map((job) => [job.id, job])))
        }

        const invalidate = (keys: readonly QueryKey[]) => {
            for (const queryKey of keys) {
                const state = queryClient.getQueryState(queryKey)
                // React Query normally reuses an unfinished initial fetch. Its snapshot may
                // predate the invalidation or reconnect, even though there is no cached data yet.
                if (state && state.data === undefined && state.fetchStatus === 'fetching') {
                    void queryClient.cancelQueries({ queryKey, exact: true })
                }
                void queryClient.invalidateQueries({ queryKey })
            }
        }

        const offConnect = onRealtimeConnect(() => {
            useRealtimeConnected.setState({ connected: true })
            invalidate(RESYNC_KEYS)
        })
        const offDisconnect = onRealtimeDisconnect((reason) => {
            useRealtimeConnected.setState({ connected: false })
            if (reason === 'io server disconnect') invalidate([queryKeys.auth])
        })
        const offInvalidate = onInvalidate((event) => {
            for (const topic of event.topics) invalidate(TOPIC_KEYS[topic] ?? [])
        })
        const onResources = (snapshot: SystemResourceSnapshot) => {
            queryClient.setQueryData(queryKeys.resources, snapshot)
        }
        realtimeSocket.on('system_resources', onResources)
        realtimeSocket.on('job_progress', onJobProgress)
        realtimeSocket.on('download_progress', onDownloadProgress)

        realtimeSocket.connect()

        return () => {
            offConnect()
            offDisconnect()
            offInvalidate()
            realtimeSocket.off('system_resources', onResources)
            realtimeSocket.off('job_progress', onJobProgress)
            realtimeSocket.off('download_progress', onDownloadProgress)
            jobs.dispose()
            downloads.dispose()
            realtimeSocket.disconnect()
            useRealtimeConnected.setState({ connected: false })
        }
    }, [queryClient])
}
