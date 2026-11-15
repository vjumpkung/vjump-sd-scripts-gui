import { getApiErrorMessage, httpStatus, retryAfterSeconds } from '@/api/client'
import { Brand } from '@/components/sidebar'
import { LanguageToggle, ThemeToggle } from '@/components/toggles'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useLogin } from '@/hooks/useAuth'
import { useI18n } from '@/i18n'
import { type FormEvent, useId, useRef, useState } from 'react'

/** The full-page password form shown instead of the app until the server accepts a login. */
const Login = () => {
    const { t } = useI18n()
    const login = useLogin()
    const [password, setPassword] = useState('')
    const inputRef = useRef<HTMLInputElement>(null)
    const id = useId()
    const errorId = useId()

    const errorMessage = () => {
        const status = httpStatus(login.error)
        if (status === 401) return t('login.wrong')
        const seconds = status === 429 ? retryAfterSeconds(login.error) : null
        if (seconds !== null) return t('login.throttled', { seconds })
        return getApiErrorMessage(login.error, t('login.failed'))
    }

    const submit = (event: FormEvent) => {
        event.preventDefault()
        if (!password || login.isPending) return
        login.mutate(password, { onError: () => inputRef.current?.select() })
    }

    return (
        <div className="relative flex min-h-screen items-center justify-center px-5 py-16">
            <div className="absolute top-4 right-4 flex items-center gap-3 sm:top-6 sm:right-6">
                <LanguageToggle />
                <ThemeToggle />
            </div>
            <main className="w-full max-w-md">
                <Brand />
                <Card className="mt-8">
                    <CardHeader>
                        <CardTitle>{t('login.title')}</CardTitle>
                        <CardDescription>{t('login.desc')}</CardDescription>
                    </CardHeader>
                    <form className="flex flex-col gap-4" onSubmit={submit}>
                        <div className="flex flex-col gap-2">
                            <Label htmlFor={id} className="text-sm font-semibold">
                                {t('login.password')}
                            </Label>
                            <Input
                                ref={inputRef}
                                id={id}
                                type="password"
                                value={password}
                                maxLength={4096}
                                autoFocus
                                autoComplete="current-password"
                                spellCheck={false}
                                aria-invalid={login.isError || undefined}
                                aria-describedby={login.isError ? errorId : undefined}
                                onChange={(event) => setPassword(event.target.value)}
                            />
                        </div>
                        {login.isError ? (
                            <p id={errorId} role="alert" className="text-sm text-destructive">
                                {errorMessage()}
                            </p>
                        ) : null}
                        <Button
                            type="submit"
                            variant="default"
                            size="lg"
                            disabled={!password || login.isPending}
                        >
                            {login.isPending ? t('login.submitting') : t('login.submit')}
                        </Button>
                    </form>
                    <p className="mt-5 text-[0.8125rem] leading-relaxed text-muted-foreground">
                        {t('login.hint')}
                    </p>
                </Card>
            </main>
        </div>
    )
}

export default Login
