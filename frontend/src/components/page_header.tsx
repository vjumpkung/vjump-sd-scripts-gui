import { cn } from '@/lib/utils'
import { type ReactNode, useEffect, useState } from 'react'

// The marker draws itself once, on the first page the visitor sees (DESIGN.md, Motion).
let markerPlayed = false

type PageHeaderProps = {
    before?: string
    // The key phrase that gets the marker highlight.
    mark: string
    after?: string
    description?: ReactNode
    actions?: ReactNode
    className?: string
}

const PageHeader = ({ before, mark, after, description, actions, className }: PageHeaderProps) => {
    const [animate] = useState(() => !markerPlayed)

    useEffect(() => {
        markerPlayed = true
    }, [])

    return (
        <header
            className={cn(
                'mb-8 flex flex-col gap-5 md:flex-row md:items-end md:justify-between',
                className
            )}
        >
            <div className="min-w-0 max-w-3xl">
                <h1 className="text-[clamp(1.875rem,1.4rem+1.9vw,2.625rem)] leading-[1.25] font-bold tracking-[-0.02em]">
                    {before}
                    <span className={cn('marker marker-yellow', animate && 'marker-animate')}>
                        {mark}
                    </span>
                    {after}
                </h1>
                {description ? (
                    <div className="mt-3 max-w-[42rem] text-[0.9375rem] leading-[1.65] text-muted-foreground">
                        {description}
                    </div>
                ) : null}
            </div>
            {actions ? (
                <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
            ) : null}
        </header>
    )
}

export default PageHeader
