import { cn } from '@/lib/utils'
import { cva, type VariantProps } from 'class-variance-authority'
import { Slot } from 'radix-ui'
import * as React from 'react'

// Category tags: a highlighter fill with ink text, plus a 1px ink border in the light theme that
// turns transparent in dark (DESIGN.md, Chips). Non-interactive pills.
const badgeVariants = cva(
    'inline-flex h-6 w-fit shrink-0 items-center justify-center gap-1 rounded-full border px-2.5 text-xs leading-none font-semibold tracking-[0.05em] whitespace-nowrap uppercase [&>svg]:pointer-events-none [&>svg]:size-3',
    {
        variants: {
            variant: {
                yellow: 'border-ink bg-brand-yellow text-ink dark:border-transparent',
                cyan: 'border-ink bg-brand-cyan text-ink dark:border-transparent',
                pink: 'border-ink bg-brand-pink text-ink dark:border-transparent',
                muted: 'border-transparent bg-muted text-muted-foreground',
                outline: 'border-border text-foreground',
                destructive: 'border-destructive text-destructive',
                // Pink Ink is the one colour that may be text.
                modified: 'border-pink-ink text-pink-ink'
            }
        },
        defaultVariants: {
            variant: 'muted'
        }
    }
)

function Badge({
    className,
    variant,
    asChild = false,
    ...props
}: React.ComponentProps<'span'> & VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
    const Comp = asChild ? Slot.Root : 'span'

    return (
        <Comp
            data-slot="badge"
            data-variant={variant}
            className={cn(badgeVariants({ variant }), className)}
            {...props}
        />
    )
}

export { Badge, badgeVariants }
