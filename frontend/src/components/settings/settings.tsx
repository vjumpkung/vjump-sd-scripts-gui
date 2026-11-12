import { queryKeys, systemApi } from '@/api/api'
import { getApiErrorMessage } from '@/api/client'
import type { SecretsUpdate, SystemStatus } from '@/api/types'
import PageHeader from '@/components/page_header'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Chip } from '@/components/ui/chip'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue
} from '@/components/ui/select'
import useAccelerationSettings, {
    type AccelerationSettings,
    dynamoBackends,
    isValidAccelerationSettings
} from '@/hooks/useAccelerationSettings'
import { useSystemStatus } from '@/hooks/useSystem'
import useTheme, { type ThemeMode } from '@/hooks/useTheme'
import { type Locale, useI18n } from '@/i18n'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCwIcon, RotateCcwIcon, SaveIcon, Trash2Icon } from 'lucide-react'
import { type ReactNode, useEffect, useId, useRef, useState } from 'react'

type SecretKey = 'hf_token' | 'wandb_api_key'

type SecretRowProps = {
    secretKey: SecretKey
    label: string
    help: string
    isSet: boolean | undefined
}

// Secrets are write-only: the field is never pre-filled and the server never returns a value.
const SecretRow = ({ secretKey, label, help, isSet }: SecretRowProps) => {
    const { t } = useI18n()
    const queryClient = useQueryClient()
    const id = useId()
    const [value, setValue] = useState('')

    const mutation = useMutation({
        mutationFn: (body: SecretsUpdate) => systemApi.saveSecrets(body),
        onSuccess: async () => {
            setValue('')
            await queryClient.invalidateQueries({ queryKey: queryKeys.status })
        }
    })

    return (
        <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2">
                <Label htmlFor={id} className="text-sm font-semibold">
                    {label}
                </Label>
                <Badge variant={isSet ? 'cyan' : 'muted'}>
                    {isSet === undefined
                        ? t('common.loading')
                        : isSet
                          ? t('settings.secret.set')
                          : t('settings.secret.notSet')}
                </Badge>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                    id={id}
                    type="password"
                    value={value}
                    maxLength={2048}
                    autoComplete="new-password"
                    spellCheck={false}
                    placeholder={isSet ? t('settings.secret.placeholderSet') : ''}
                    onChange={(event) => setValue(event.target.value)}
                />
                <div className="flex gap-2">
                    <Button
                        variant="default"
                        disabled={!value.trim() || mutation.isPending}
                        onClick={() => mutation.mutate({ [secretKey]: value.trim() })}
                    >
                        <SaveIcon />
                        {t('common.save')}
                    </Button>
                    <Button
                        variant="outline"
                        disabled={!isSet || mutation.isPending}
                        onClick={() => mutation.mutate({ [secretKey]: null })}
                    >
                        <Trash2Icon />
                        {t('settings.secret.clear')}
                    </Button>
                </div>
            </div>
            <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">{help}</p>
            {mutation.error ? (
                <p role="alert" className="text-sm text-destructive">
                    {getApiErrorMessage(mutation.error, t('settings.secret.error'))}
                </p>
            ) : null}
        </div>
    )
}

type NumberSettingProps = {
    label: string
    help: string
    settingKey: keyof AccelerationSettings
    value: string
    onChange: (key: keyof AccelerationSettings, value: string) => void
}

const NumberSetting = ({ label, help, settingKey, value, onChange }: NumberSettingProps) => {
    const { t } = useI18n()
    const id = useId()
    const invalid = !/^[1-9]\d*$/.test(value.trim())

    return (
        <div className="flex flex-col gap-2">
            <Label htmlFor={id} className="text-sm font-semibold">
                {label}
            </Label>
            <Input
                id={id}
                value={value}
                inputMode="numeric"
                autoComplete="off"
                aria-invalid={invalid || undefined}
                onChange={(event) => onChange(settingKey, event.target.value)}
            />
            <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">{help}</p>
            {invalid ? (
                <p role="alert" className="text-sm text-destructive">
                    {t('validation.positiveInt')}
                </p>
            ) : null}
        </div>
    )
}

const InfoRow = ({ label, children }: { label: string; children: ReactNode }) => (
    <div className="flex flex-col gap-1 border-b border-border py-3 first:pt-0 last:border-b-0 last:pb-0 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
        <dt className="shrink-0 text-sm text-muted-foreground">{label}</dt>
        <dd className="min-w-0 text-sm font-medium break-all sm:text-right">{children}</dd>
    </div>
)

const EnvironmentCard = ({ status }: { status: SystemStatus | undefined }) => {
    const { t } = useI18n()
    const queryClient = useQueryClient()
    const rescan = status?.schema.rescan
    const running = rescan?.state === 'running'

    const rescanMutation = useMutation({
        mutationFn: systemApi.rescan,
        onSuccess: (next) => queryClient.setQueryData(queryKeys.status, next)
    })

    // When a rescan finishes the argument schema may have changed: drop every cached copy.
    const wasRunning = useRef(false)
    useEffect(() => {
        if (wasRunning.current && !running) {
            void queryClient.invalidateQueries({ queryKey: ['schema'] })
            void queryClient.invalidateQueries({ queryKey: queryKeys.presets })
        }
        wasRunning.current = running
    }, [running, queryClient])

    const mono = (text: string | null | undefined) => (
        <span className="font-mono text-[0.8125rem]" translate="no">
            {text || '-'}
        </span>
    )

    return (
        <Card>
            <CardHeader>
                <CardTitle>{t('settings.env.title')}</CardTitle>
                <CardDescription>{t('settings.env.desc')}</CardDescription>
            </CardHeader>
            <dl className="flex flex-col">
                <InfoRow label={t('settings.env.dir')}>{mono(status?.sd_scripts.dir)}</InfoRow>
                <InfoRow label={t('settings.env.python')}>
                    {mono(status?.sd_scripts.python)}
                </InfoRow>
                <InfoRow label={t('settings.env.pythonOk')}>
                    {status ? (
                        <Badge variant={status.sd_scripts.python_ok ? 'cyan' : 'destructive'}>
                            {status.sd_scripts.python_ok ? t('common.yes') : t('common.no')}
                        </Badge>
                    ) : (
                        '-'
                    )}
                </InfoRow>
                <InfoRow label={t('settings.env.commit')}>
                    {mono(status?.sd_scripts.commit?.slice(0, 10))}
                </InfoRow>
                <InfoRow label={t('settings.env.schemaSource')}>
                    {mono(status?.schema.source)}
                </InfoRow>
                <InfoRow label={t('settings.env.schemaCommit')}>
                    {mono(status?.schema.commit?.slice(0, 10))}
                </InfoRow>
                <InfoRow label={t('settings.env.stale')}>
                    {status ? (
                        <Badge variant={status.schema.stale ? 'pink' : 'muted'}>
                            {status.schema.stale ? t('common.yes') : t('common.no')}
                        </Badge>
                    ) : (
                        '-'
                    )}
                </InfoRow>
            </dl>
            <div className="mt-5 flex flex-col gap-3 border-t border-border pt-5">
                <div className="flex flex-wrap items-center gap-3">
                    <Button
                        variant="default"
                        disabled={running || rescanMutation.isPending || !status}
                        onClick={() => rescanMutation.mutate()}
                    >
                        <RefreshCwIcon
                            className={running ? 'motion-safe:animate-spin' : undefined}
                        />
                        {running ? t('settings.env.rescanning') : t('settings.env.rescan')}
                    </Button>
                    <span
                        className="text-sm text-muted-foreground"
                        role="status"
                        aria-live="polite"
                    >
                        {running ? t('settings.env.rescanHint') : ''}
                    </span>
                </div>
                {rescan?.state === 'failed' ? (
                    <Alert variant="destructive">
                        <AlertDescription className="mt-0">
                            {t('settings.env.rescanFailed')}
                            {rescan.error ? `: ${rescan.error}` : ''}
                        </AlertDescription>
                    </Alert>
                ) : null}
                {rescanMutation.error ? (
                    <p role="alert" className="text-sm text-destructive">
                        {getApiErrorMessage(rescanMutation.error, t('settings.env.rescanError'))}
                    </p>
                ) : null}
            </div>
        </Card>
    )
}

const THEME_MODES: ThemeMode[] = ['system', 'light', 'dark']
const LOCALES: Array<{ value: Locale; label: string }> = [
    { value: 'en', label: 'English' },
    { value: 'th', label: 'ไทย' }
]

const Settings = () => {
    const { t, locale, setLocale } = useI18n()
    const status = useSystemStatus()
    const settings = useAccelerationSettings((state) => state.settings)
    const setSetting = useAccelerationSettings((state) => state.setSetting)
    const resetSettings = useAccelerationSettings((state) => state.resetSettings)
    const mode = useTheme((state) => state.mode)
    const setMode = useTheme((state) => state.setMode)
    const dynamoId = useId()

    return (
        <div>
            <PageHeader
                mark={t('settings.title.mark')}
                after={t('settings.title.after')}
                description={t('settings.subtitle')}
            />

            {status.isError ? (
                <Alert variant="destructive" className="mb-6">
                    <AlertDescription className="mt-0">
                        {getApiErrorMessage(status.error, t('settings.statusError'))}
                    </AlertDescription>
                </Alert>
            ) : null}

            <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
                <div className="flex min-w-0 flex-col gap-6">
                    <Card>
                        <CardHeader>
                            <CardTitle>{t('settings.secrets.title')}</CardTitle>
                            <CardDescription>{t('settings.secrets.desc')}</CardDescription>
                        </CardHeader>
                        <div className="flex flex-col gap-6">
                            <SecretRow
                                secretKey="hf_token"
                                label={t('settings.secret.hf')}
                                help={t('settings.secret.hf.help')}
                                isSet={status.data?.secrets.hf_token}
                            />
                            <SecretRow
                                secretKey="wandb_api_key"
                                label={t('settings.secret.wandb')}
                                help={t('settings.secret.wandb.help')}
                                isSet={status.data?.secrets.wandb_api_key}
                            />
                        </div>
                    </Card>

                    <Card>
                        <CardHeader className="flex-row items-start justify-between gap-3">
                            <div className="flex flex-col gap-1">
                                <CardTitle>{t('settings.accelerate.title')}</CardTitle>
                                <CardDescription>{t('settings.accelerate.desc')}</CardDescription>
                            </div>
                            <Button variant="outline" onClick={resetSettings}>
                                <RotateCcwIcon />
                                {t('settings.accelerate.restore')}
                            </Button>
                        </CardHeader>
                        <div className="grid gap-6 sm:grid-cols-2">
                            <NumberSetting
                                label={t('settings.accelerate.processes')}
                                help={t('settings.accelerate.processes.help')}
                                settingKey="numProcesses"
                                value={settings.numProcesses}
                                onChange={setSetting}
                            />
                            <NumberSetting
                                label={t('settings.accelerate.machines')}
                                help={t('settings.accelerate.machines.help')}
                                settingKey="numMachines"
                                value={settings.numMachines}
                                onChange={setSetting}
                            />
                            <NumberSetting
                                label={t('settings.accelerate.threads')}
                                help={t('settings.accelerate.threads.help')}
                                settingKey="numCpuThreadsPerProcess"
                                value={settings.numCpuThreadsPerProcess}
                                onChange={setSetting}
                            />
                            <div className="flex flex-col gap-2">
                                <Label htmlFor={dynamoId} className="text-sm font-semibold">
                                    {t('settings.accelerate.dynamo')}
                                </Label>
                                <Select
                                    value={settings.dynamoBackend}
                                    onValueChange={(next) => setSetting('dynamoBackend', next)}
                                >
                                    <SelectTrigger id={dynamoId}>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {dynamoBackends.map((backend) => (
                                            <SelectItem key={backend} value={backend}>
                                                <span translate="no">{backend}</span>
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                <p className="text-[0.8125rem] leading-relaxed text-muted-foreground">
                                    {t('settings.accelerate.dynamo.help')}
                                </p>
                            </div>
                        </div>
                        {!isValidAccelerationSettings(settings) ? (
                            <p role="alert" className="mt-4 text-sm text-destructive">
                                {t('settings.accelerate.invalid')}
                            </p>
                        ) : null}
                        <p className="mt-4 text-[0.8125rem] leading-relaxed text-muted-foreground">
                            {t('settings.accelerate.saved')}
                        </p>
                    </Card>
                </div>

                <div className="flex min-w-0 flex-col gap-6">
                    <EnvironmentCard status={status.data} />

                    <Card>
                        <CardHeader>
                            <CardTitle>{t('settings.appearance.title')}</CardTitle>
                            <CardDescription>{t('settings.appearance.desc')}</CardDescription>
                        </CardHeader>
                        <div className="flex flex-col gap-5">
                            <div className="flex flex-col gap-2">
                                <p className="text-sm font-semibold">{t('settings.language')}</p>
                                <div
                                    role="group"
                                    aria-label={t('settings.language')}
                                    className="flex flex-wrap gap-2"
                                >
                                    {LOCALES.map((item) => (
                                        <Chip
                                            key={item.value}
                                            active={locale === item.value}
                                            lang={item.value}
                                            onClick={() => setLocale(item.value)}
                                        >
                                            {item.label}
                                        </Chip>
                                    ))}
                                </div>
                            </div>
                            <div className="flex flex-col gap-2">
                                <p className="text-sm font-semibold">{t('settings.theme')}</p>
                                <div
                                    role="group"
                                    aria-label={t('settings.theme')}
                                    className="flex flex-wrap gap-2"
                                >
                                    {THEME_MODES.map((item) => (
                                        <Chip
                                            key={item}
                                            active={mode === item}
                                            onClick={() => setMode(item)}
                                        >
                                            {t(`settings.theme.${item}`)}
                                        </Chip>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>{t('settings.workspace.title')}</CardTitle>
                            <CardDescription>{t('settings.workspace.desc')}</CardDescription>
                        </CardHeader>
                        <dl className="flex flex-col">
                            <InfoRow label={t('settings.workspace.root')}>
                                <span className="font-mono text-[0.8125rem]" translate="no">
                                    {status.data?.workspace_root ?? '-'}
                                </span>
                            </InfoRow>
                            <InfoRow label={t('settings.auth')}>
                                {status.data ? (
                                    <Badge variant={status.data.auth ? 'cyan' : 'muted'}>
                                        {status.data.auth
                                            ? t('settings.auth.on')
                                            : t('settings.auth.off')}
                                    </Badge>
                                ) : (
                                    '-'
                                )}
                            </InfoRow>
                        </dl>
                        <p className="mt-4 text-[0.8125rem] leading-relaxed text-muted-foreground">
                            {status.data?.auth
                                ? t('settings.auth.onNote')
                                : t('settings.auth.offNote')}
                        </p>
                    </Card>
                </div>
            </div>
        </div>
    )
}

export default Settings
