import { presetsApi, queryKeys, systemApi } from '../api/api'
import { useQuery } from '@tanstack/react-query'

/** System status. Polls only while a schema rescan is running. */
export const useSystemStatus = () =>
    useQuery({
        queryKey: queryKeys.status,
        queryFn: systemApi.status,
        staleTime: 5_000,
        refetchInterval: (query) =>
            query.state.data?.schema.rescan.state === 'running' ? 1_500 : false
    })

/** The preset catalog. It only changes when the backend is updated. */
export const usePresets = () =>
    useQuery({
        queryKey: queryKeys.presets,
        queryFn: presetsApi.list,
        staleTime: 5 * 60_000
    })
