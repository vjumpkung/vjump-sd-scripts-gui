import { cn } from '@/lib/utils'
import { Tabs as TabsPrimitive } from 'radix-ui'
import * as React from 'react'

function Tabs({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Root>) {
    return (
        <TabsPrimitive.Root
            data-slot="tabs"
            className={cn('flex flex-col', className)}
            {...props}
        />
    )
}

function TabsList({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.List>) {
    return (
        <TabsPrimitive.List
            data-slot="tabs-list"
            className={cn('flex flex-wrap gap-2', className)}
            {...props}
        />
    )
}

// The active tab is the Highlighter Yellow pill with ink text (DESIGN.md, nav-tab-active).
function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
    return (
        <TabsPrimitive.Trigger
            data-slot="tabs-trigger"
            className={cn(
                'inline-flex h-10 items-center justify-center gap-2 rounded-full px-4 text-sm font-medium whitespace-nowrap text-muted-foreground transition-colors outline-none hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-50 data-[state=active]:bg-primary data-[state=active]:text-ink motion-reduce:transition-none [&_svg]:size-4 [&_svg]:shrink-0',
                className
            )}
            {...props}
        />
    )
}

function TabsContent({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Content>) {
    return (
        <TabsPrimitive.Content
            data-slot="tabs-content"
            className={cn('outline-none', className)}
            {...props}
        />
    )
}

export { Tabs, TabsContent, TabsList, TabsTrigger }
