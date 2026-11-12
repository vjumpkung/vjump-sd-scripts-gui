import { Button } from '@/components/ui/button'
import useTheme from '@/hooks/useTheme'
import { type Locale, useI18n } from '@/i18n'
import { cn } from '@/lib/utils'
import { MoonIcon, SunIcon } from 'lucide-react'

const LOCALES: Array<{ value: Locale; label: string }> = [
    { value: 'en', label: 'EN' },
    { value: 'th', label: 'TH' }
]

/** EN | TH pill toggle. The active side is a solid inversion, like a filter chip. */
export const LanguageToggle = ({ className }: { className?: string }) => {
    const { locale, setLocale, t } = useI18n()

    return (
        <div
            role="group"
            aria-label={t('nav.language')}
            className={cn(
                'inline-flex h-10 items-center rounded-full border border-input bg-card p-0.5',
                className
            )}
        >
            {LOCALES.map((item) => (
                <button
                    key={item.value}
                    type="button"
                    lang={item.value}
                    aria-pressed={locale === item.value}
                    className={cn(
                        'h-full min-w-12 rounded-full px-3 text-sm font-medium transition-colors motion-reduce:transition-none',
                        locale === item.value
                            ? 'bg-foreground text-background'
                            : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                    )}
                    onClick={() => setLocale(item.value)}
                >
                    {item.label}
                </button>
            ))}
        </div>
    )
}

/** An outlined 40px circle whose border turns Highlighter Pink on hover (DESIGN.md, Buttons). */
export const ThemeToggle = ({ className }: { className?: string }) => {
    const { t } = useI18n()
    const dark = useTheme((state) => state.dark)
    const toggle = useTheme((state) => state.toggle)
    const label = dark ? t('nav.theme.toLight') : t('nav.theme.toDark')

    return (
        <Button
            variant="outline"
            size="icon"
            aria-label={label}
            title={label}
            className={cn('hover:border-brand-pink', className)}
            onClick={toggle}
        >
            {dark ? <SunIcon className="size-[18px]" /> : <MoonIcon className="size-[18px]" />}
        </Button>
    )
}
