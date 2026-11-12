import { downloadsApi, queryKeys } from '../api/api'
import { useQuery } from '@tanstack/react-query'

/** The download catalog, including which files are already present in the workspace. */
export const useCatalog = () =>
    useQuery({
        queryKey: queryKeys.catalog,
        queryFn: downloadsApi.catalog,
        staleTime: 10_000
    })
