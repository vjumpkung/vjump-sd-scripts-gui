import { presetsApi, queryKeys, systemApi } from '../api/api'
import { useRealtimeConnected } from './useRealtime'
import { useQuery } from '@tanstack/react-query'

/** System status. Polls only while a schema rescan is running and the realtime channel is down. */
export const useSystemStatus = () => {
    const connected = useRealtimeConnected((state) => state.connected)

    return useQuery({
        queryKey: queryKeys.status,
        queryFn: systemApi.status,
        staleTime: 5_000,
        refetchInterval: (query) =>
            !connected && query.state.data?.schema.rescan.state === 'running' ? 1_500 : false
    })
}

/** The preset catalog. It only changes when the backend is updated. */
export const usePresets = () =>
    useQuery({
        queryKey: queryKeys.presets,
        queryFn: presetsApi.list,
        staleTime: 5 * 60_000
    })
