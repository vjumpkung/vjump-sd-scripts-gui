import { cn } from '@/lib/utils'
import * as React from 'react'

// Flat sheets: Note Card fill, Hairline border, 14px corners, 24px padding, no shadow.
function Card({
    className,
    compact = false,
    ...props
}: React.ComponentProps<'div'> & { compact?: boolean }) {
    return (
        <div
            data-slot="card"
            className={cn(
                'rounded-xl border border-border bg-card text-card-foreground',
                compact ? 'p-5' : 'p-6',
                className
            )}
            {...props}
        />
    )
}

function CardHeader({ className, ...props }: React.ComponentProps<'div'>) {
    return (
        <div
            data-slot="card-header"
            className={cn('mb-5 flex flex-col gap-1', className)}
            {...props}
        />
    )
}

function CardTitle({ className, ...props }: React.ComponentProps<'h2'>) {
    return (
        <h2
            data-slot="card-title"
            className={cn('text-xl leading-[1.4] font-bold', className)}
            {...props}
        />
    )
}

function CardDescription({ className, ...props }: React.ComponentProps<'p'>) {
    return (
        <p
            data-slot="card-description"
            className={cn('text-sm leading-relaxed text-muted-foreground', className)}
            {...props}
        />
    )
}

function CardContent({ className, ...props }: React.ComponentProps<'div'>) {
    return <div data-slot="card-content" className={className} {...props} />
}

function CardFooter({ className, ...props }: React.ComponentProps<'div'>) {
    return (
        <div
            data-slot="card-footer"
            className={cn(
                'mt-5 flex flex-wrap items-center gap-2 border-t border-border pt-5',
                className
            )}
            {...props}
        />
    )
}

export { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle }
