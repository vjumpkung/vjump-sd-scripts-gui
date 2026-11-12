import App from './App'
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

initTheme()
initLocale()

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
    <React.StrictMode>
        <QueryClientProvider client={queryClient}>
            <TooltipProvider>
                <App />
            </TooltipProvider>
        </QueryClientProvider>
    </React.StrictMode>
)
