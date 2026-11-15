import { authApi, queryKeys } from '../api/api'
import type { AuthStatus } from '../api/types'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

/** Whether the server wants a password and whether this browser has a valid session. */
export const useAuthStatus = () =>
    useQuery({
        queryKey: queryKeys.auth,
        queryFn: authApi.status,
        // Changes only through login, logout or a 401 (see main.tsx), never by itself.
        staleTime: Infinity
    })

export const useLogin = () => {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (password: string) => authApi.login({ password }),
        onSuccess: async () => {
            queryClient.setQueryData<AuthStatus>(queryKeys.auth, {
                auth_required: true,
                authenticated: true
            })
            // Whatever failed with 401 while logged out has to be fetched again.
            await queryClient.invalidateQueries()
        }
    })
}

export const useLogout = () => {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: authApi.logout,
        onSuccess: () => {
            // The gate watches the auth entry, so it is updated in place and not cleared.
            queryClient.setQueryData<AuthStatus>(queryKeys.auth, {
                auth_required: true,
                authenticated: false
            })
            queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== 'auth' })
        }
    })
}
