import PageHeader from '@/components/page_header'
import { Badge } from '@/components/ui/badge'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useSystemStatus } from '@/hooks/useSystem'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'
import { ArrowUpRightIcon, GlobeIcon, MailIcon, MessageCircleIcon } from 'lucide-react'
import type { ReactNode } from 'react'

type LinkCardProps = { href: string; title: string; description: string }

// Link Card: the border strengthens on hover, the title turns Pink Ink, the arrow nudges 2px.
const LinkCard = ({ href, title, description }: LinkCardProps) => (
    <a
        href={href}
        target="_blank"
        rel="noreferrer"
        className="group/link flex flex-col gap-1 rounded-xl border border-border bg-card p-5 transition-colors hover:border-input motion-reduce:transition-none"
    >
        <span className="flex items-center justify-between gap-3">
            <span
                className="font-semibold transition-colors group-hover/link:text-pink-ink motion-reduce:transition-none"
                translate="no"
            >
                {title}
            </span>
            <ArrowUpRightIcon
                aria-hidden
                className="size-4 shrink-0 text-muted-foreground transition-transform group-hover/link:translate-x-0.5 group-hover/link:-translate-y-0.5 motion-reduce:transition-none"
            />
        </span>
        <span className="text-sm leading-relaxed text-muted-foreground">{description}</span>
    </a>
)

type ContactRowProps = {
    href: string
    icon: ReactNode
    label: string
    value: string
    // Each row keeps its own highlighter tone, always with ink text on hover.
    tone: 'yellow' | 'cyan' | 'pink'
    external?: boolean
}

const TONE_HOVER = {
    yellow: 'hover:bg-brand-yellow',
    cyan: 'hover:bg-brand-cyan',
    pink: 'hover:bg-brand-pink'
} as const

const ContactRow = ({ href, icon, label, value, tone, external = true }: ContactRowProps) => (
    <a
        href={href}
        {...(external ? { target: '_blank', rel: 'noreferrer' } : {})}
        className={cn(
            'flex h-11 items-center gap-3 rounded-lg bg-background px-4 text-sm font-medium transition-colors hover:text-ink motion-reduce:transition-none',
            TONE_HOVER[tone]
        )}
    >
        <span aria-hidden className="shrink-0 [&_svg]:size-[18px]">
            {icon}
        </span>
        <span className="shrink-0">{label}</span>
        <span className="ml-auto min-w-0 truncate text-right opacity-80" translate="no">
            {value}
        </span>
    </a>
)

const About = () => {
    const { t } = useI18n()
    const status = useSystemStatus()

    return (
        <div>
            <PageHeader
                before={t('about.title.before')}
                mark={t('app.name')}
                description={t('about.lede')}
            />

            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)] lg:items-start">
                <div className="flex min-w-0 flex-col gap-6">
                    <Card>
                        <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
                            <img
                                src="/logo.png"
                                alt={t('about.logoAlt')}
                                className="size-24 shrink-0 rounded-xl object-contain"
                            />
                            <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-3">
                                    <h2 className="text-xl leading-[1.4] font-bold">
                                        {t('app.name')}
                                    </h2>
                                    <Badge variant="outline" translate="no">
                                        {status.data ? `v${status.data.version}` : 'v-'}
                                    </Badge>
                                </div>
                                <p className="text-sm text-muted-foreground">{t('app.by')}</p>
                            </div>
                        </div>
                        <p className="mt-5 max-w-[44rem] text-base leading-[1.85]">
                            {t('about.body')}
                        </p>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>{t('about.credits.title')}</CardTitle>
                            <CardDescription>{t('about.credits.desc')}</CardDescription>
                        </CardHeader>
                        <div className="grid gap-4 sm:grid-cols-2">
                            <LinkCard
                                href="https://github.com/kohya-ss/sd-scripts"
                                title="kohya-ss/sd-scripts"
                                description={t('about.credits.upstream')}
                            />
                            <LinkCard
                                href="https://github.com/vjumpkung/sd-scripts"
                                title="vjumpkung/sd-scripts"
                                description={t('about.credits.fork')}
                            />
                        </div>
                        <p className="mt-5 text-sm leading-relaxed text-muted-foreground">
                            {t('about.credits.lineage')}
                        </p>
                    </Card>
                </div>

                <Card>
                    <CardHeader>
                        <CardTitle>{t('about.contact.title')}</CardTitle>
                        <CardDescription>{t('about.contact.desc')}</CardDescription>
                    </CardHeader>
                    <div className="flex flex-col gap-2">
                        <ContactRow
                            href="https://www.facebook.com/pixellatent"
                            icon={<MessageCircleIcon />}
                            label={t('about.contact.facebook')}
                            value="pixellatent"
                            tone="yellow"
                        />
                        <ContactRow
                            href="mailto:vjumpkung@gmail.com"
                            icon={<MailIcon />}
                            label={t('about.contact.email')}
                            value="vjumpkung@gmail.com"
                            tone="cyan"
                            external={false}
                        />
                        <ContactRow
                            href="https://vjump.dev"
                            icon={<GlobeIcon />}
                            label={t('about.contact.website')}
                            value="vjump.dev"
                            tone="pink"
                        />
                    </div>
                </Card>
            </div>
        </div>
    )
}

export default About
