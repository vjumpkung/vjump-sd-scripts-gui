import { cn } from '@/lib/utils'
import { Label as LabelPrimitive } from 'radix-ui'
import * as React from 'react'

function Label({ className, ...props }: React.ComponentProps<typeof LabelPrimitive.Root>) {
    return (
        <LabelPrimitive.Root
            data-slot="label"
            className={cn(
                'flex items-center gap-2 text-[0.8125rem] leading-normal font-medium select-none peer-disabled:cursor-not-allowed peer-disabled:opacity-50',
                className
            )}
            {...props}
        />
    )
}

export { Label }
