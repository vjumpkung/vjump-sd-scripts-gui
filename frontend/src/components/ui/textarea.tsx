import { cn } from '@/lib/utils'
import * as React from 'react'

function Textarea({ className, ...props }: React.ComponentProps<'textarea'>) {
    return (
        <textarea
            data-slot="textarea"
            className={cn(
                'flex min-h-24 w-full rounded-lg border border-input bg-card px-3 py-2.5 text-base text-foreground transition-colors outline-none placeholder:text-muted-foreground focus-visible:border-ring disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive sm:text-sm',
                className
            )}
            {...props}
        />
    )
}

export { Textarea }
