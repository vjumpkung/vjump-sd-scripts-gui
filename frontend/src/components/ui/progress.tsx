import { cn } from '@/lib/utils'
import { Progress as ProgressPrimitive } from 'radix-ui'
import * as React from 'react'

// Graphite fill on a Muted Wash track keeps the bar readable; the pastels stay for tags and marks.
function Progress({
    className,
    value,
    ...props
}: React.ComponentProps<typeof ProgressPrimitive.Root>) {
    const clamped = Math.min(100, Math.max(0, value ?? 0))

    return (
        <ProgressPrimitive.Root
            data-slot="progress"
            value={value}
            className={cn(
                'relative h-2 w-full overflow-hidden rounded-full border border-border bg-muted',
                className
            )}
            {...props}
        >
            <ProgressPrimitive.Indicator
                data-slot="progress-indicator"
                className="size-full flex-1 bg-foreground transition-transform motion-reduce:transition-none"
                style={{ transform: `translateX(-${100 - clamped}%)` }}
            />
        </ProgressPrimitive.Root>
    )
}

export { Progress }
