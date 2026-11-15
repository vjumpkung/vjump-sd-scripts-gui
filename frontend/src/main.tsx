import App from './App'
import { queryKeys } from './api/api'
import { setUnauthorizedHandler } from './api/client'
import type { AuthStatus } from './api/types'
import AuthGate from './components/auth_gate'
import './index.css'
import { TooltipProvider } from '@/components/ui/tooltip'
import { initTheme } from '@/hooks/useTheme'
import { initLocale } from '@/i18n'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import ReactDOM from 'react-dom/client'

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 1_000,
            retry: 1,
            refetchOnWindowFocus: false
        },
        mutations: {
            retry: 0
        }
    }
})

// A 401 outside the login form means the session ended: send the user back to the login page.
setUnauthorizedHandler(() => {
    queryClient.setQueryData<AuthStatus>(queryKeys.auth, {
        auth_required: true,
        authenticated: false
    })
})

initTheme()
initLocale()

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
    <React.StrictMode>
        <QueryClientProvider client={queryClient}>
            <TooltipProvider>
                <AuthGate>
                    <App />
                </AuthGate>
            </TooltipProvider>
        </QueryClientProvider>
    </React.StrictMode>
)
