import Login from './login/login'
import { Button } from './ui/button'
import { Card } from './ui/card'
import { getApiErrorMessage } from '@/api/client'
import { useAuthStatus } from '@/hooks/useAuth'
import { useI18n } from '@/i18n'
import type { ReactNode } from 'react'

/** Shows the login page instead of the app while the server wants a password and has none. */
const AuthGate = ({ children }: { children: ReactNode }) => {
    const { t } = useI18n()
    const status = useAuthStatus()

    if (!status.data) {
        if (!status.isError) {
            return (
                <div className="flex min-h-screen items-center justify-center px-5">
                    <p role="status" className="text-sm text-muted-foreground">
                        {t('common.loading')}
                    </p>
                </div>
            )
        }
        return (
            <div className="flex min-h-screen items-center justify-center px-5">
                <Card className="flex w-full max-w-md flex-col items-start gap-4">
                    <p role="alert" className="text-sm text-destructive">
                        {getApiErrorMessage(status.error, t('login.unreachable'))}
                    </p>
                    <Button
                        variant="default"
                        disabled={status.isFetching}
                        onClick={() => void status.refetch()}
                    >
                        {t('common.retry')}
                    </Button>
                </Card>
            </div>
        )
    }

    if (status.data.auth_required && !status.data.authenticated) return <Login />
    return <>{children}</>
}

export default AuthGate
