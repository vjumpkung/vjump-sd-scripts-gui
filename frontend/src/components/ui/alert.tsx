import { cn } from '@/lib/utils'
import { cva, type VariantProps } from 'class-variance-authority'
import * as React from 'react'

// A callout: Callout Tint fill, 14px corners, no border. `destructive` is for errors only.
const alertVariants = cva('w-full rounded-xl px-5 py-4 text-sm leading-relaxed', {
    variants: {
        variant: {
            note: 'bg-note text-foreground',
            destructive: 'border border-destructive bg-card text-destructive'
        }
    },
    defaultVariants: {
        variant: 'note'
    }
})

function Alert({
    className,
    variant,
    role,
    ...props
}: React.ComponentProps<'div'> & VariantProps<typeof alertVariants>) {
    return (
        <div
            data-slot="alert"
            role={role ?? (variant === 'destructive' ? 'alert' : 'status')}
            className={cn(alertVariants({ variant }), className)}
            {...props}
        />
    )
}

function AlertTitle({ className, ...props }: React.ComponentProps<'p'>) {
    return <p data-slot="alert-title" className={cn('font-semibold', className)} {...props} />
}

function AlertDescription({ className, ...props }: React.ComponentProps<'div'>) {
    return (
        <div
            data-slot="alert-description"
            className={cn(
                'mt-1 [&_a]:font-medium [&_a]:underline [&_a]:decoration-pink-ink [&_a]:underline-offset-[0.22em]',
                className
            )}
            {...props}
        />
    )
}

export { Alert, AlertDescription, AlertTitle }
