import { cn } from '@/lib/utils'
import { cva, type VariantProps } from 'class-variance-authority'
import { Slot } from 'radix-ui'
import * as React from 'react'

// Pill buttons, 40px tall (DESIGN.md, Buttons). Colour only arrives on interaction, except for the
// Highlighter Yellow `default` variant which marks the one action a page wants attention on.
const buttonVariants = cva(
    "inline-flex shrink-0 items-center justify-center gap-2 rounded-full border border-transparent text-sm font-medium whitespace-nowrap transition-colors duration-150 outline-none select-none motion-reduce:transition-none active:translate-y-px motion-reduce:active:translate-y-0 disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
    {
        variants: {
            variant: {
                default: 'bg-primary text-ink hover:bg-[color-mix(in_srgb,var(--primary),#000_8%)]',
                outline: 'border-input bg-card text-foreground hover:bg-muted',
                secondary:
                    'bg-secondary text-ink hover:bg-[color-mix(in_srgb,var(--secondary),#000_8%)]',
                inverse: 'bg-foreground text-background hover:opacity-90',
                ghost: 'text-foreground hover:bg-muted',
                destructive: 'border-destructive bg-card text-destructive hover:bg-destructive/10',
                link: 'h-auto rounded-sm px-0 text-foreground underline decoration-pink-ink decoration-[0.08em] underline-offset-[0.22em] hover:decoration-[0.16em]'
            },
            size: {
                default: 'h-10 px-4',
                lg: 'h-11 px-5',
                icon: 'size-10 p-0',
                // The 32px square exists only for controls that sit inside a code block.
                'icon-sm': 'size-8 rounded-md p-0'
            }
        },
        defaultVariants: {
            variant: 'outline',
            size: 'default'
        }
    }
)

function Button({
    className,
    variant,
    size,
    asChild = false,
    type,
    ...props
}: React.ComponentProps<'button'> &
    VariantProps<typeof buttonVariants> & {
        asChild?: boolean
    }) {
    const Comp = asChild ? Slot.Root : 'button'

    return (
        <Comp
            data-slot="button"
            type={asChild ? type : (type ?? 'button')}
            className={cn(
                buttonVariants({ variant, size }),
                variant === 'link' && 'size-auto',
                className
            )}
            {...props}
        />
    )
}

export { Button, buttonVariants }
