import { cn } from '@/lib/utils'
import * as React from 'react'

function Input({ className, type, ...props }: React.ComponentProps<'input'>) {
    return (
        <input
            type={type}
            data-slot="input"
            className={cn(
                'h-11 w-full min-w-0 rounded-lg border border-input bg-card px-3 text-base text-foreground transition-colors outline-none placeholder:text-muted-foreground focus-visible:border-ring disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive sm:text-sm',
                className
            )}
            {...props}
        />
    )
}

export { Input }
