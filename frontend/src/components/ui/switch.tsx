import { cn } from '@/lib/utils'
import { Switch as SwitchPrimitive } from 'radix-ui'
import * as React from 'react'

// The track keeps the Control Outline border so the control is identifiable on any surface.
function Switch({ className, ...props }: React.ComponentProps<typeof SwitchPrimitive.Root>) {
    return (
        <SwitchPrimitive.Root
            data-slot="switch"
            className={cn(
                'peer inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border border-input bg-card p-0.5 transition-colors outline-none disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary motion-reduce:transition-none',
                className
            )}
            {...props}
        >
            <SwitchPrimitive.Thumb
                data-slot="switch-thumb"
                className="pointer-events-none block size-[18px] rounded-full bg-muted-foreground transition-transform data-[state=checked]:translate-x-5 data-[state=checked]:bg-ink motion-reduce:transition-none"
            />
        </SwitchPrimitive.Root>
    )
}

export { Switch }
