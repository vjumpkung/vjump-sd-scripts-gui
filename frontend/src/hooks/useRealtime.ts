import { queryKeys } from '@/api/api'
import {
    onInvalidate,
    onRealtimeConnect,
    onRealtimeDisconnect,
    realtimeSocket
} from '@/api/realtime'
import type { RealtimeTopic, SystemResourceSnapshot } from '@/api/types'
import { type QueryKey, useQueryClient } from '@tanstack/react-query'
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

/** Opens the realtime channel and turns server pushes into query invalidations. Mount once. */
export const useRealtimeSync = () => {
    const queryClient = useQueryClient()

    useEffect(() => {
        const invalidate = (keys: readonly QueryKey[]) => {
            for (const queryKey of keys) void queryClient.invalidateQueries({ queryKey })
        }

        const offConnect = onRealtimeConnect(() => {
            useRealtimeConnected.setState({ connected: true })
            invalidate(RESYNC_KEYS)
        })
        const offDisconnect = onRealtimeDisconnect(() => {
            useRealtimeConnected.setState({ connected: false })
        })
        const offInvalidate = onInvalidate((event) => {
            for (const topic of event.topics) invalidate(TOPIC_KEYS[topic] ?? [])
        })
        const onResources = (snapshot: SystemResourceSnapshot) => {
            queryClient.setQueryData(queryKeys.resources, snapshot)
        }
        realtimeSocket.on('system_resources', onResources)

        realtimeSocket.connect()

        return () => {
            offConnect()
            offDisconnect()
            offInvalidate()
            realtimeSocket.off('system_resources', onResources)
            realtimeSocket.disconnect()
            useRealtimeConnected.setState({ connected: false })
        }
    }, [queryClient])
}
