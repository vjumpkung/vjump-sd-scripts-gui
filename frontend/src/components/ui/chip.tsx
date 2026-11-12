import { cn } from '@/lib/utils'
import * as React from 'react'

// A filter chip. Active is a solid inversion (foreground fill, page-colour text), not an accent.
function Chip({
    active = false,
    className,
    type = 'button',
    ...props
}: React.ComponentProps<'button'> & { active?: boolean }) {
    return (
        <button
            type={type}
            data-slot="chip"
            aria-pressed={active}
            className={cn(
                'inline-flex h-10 items-center justify-center gap-2 rounded-full border px-4 text-sm font-medium whitespace-nowrap uppercase transition-colors outline-none disabled:pointer-events-none disabled:opacity-50 motion-reduce:transition-none',
                active
                    ? 'border-transparent bg-foreground text-background'
                    : 'border-input bg-card text-foreground hover:bg-muted',
                className
            )}
            {...props}
        />
    )
}

export { Chip }
