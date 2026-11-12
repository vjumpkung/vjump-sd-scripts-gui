import { cn } from '@/lib/utils'
import { ChevronDownIcon } from 'lucide-react'
import { Accordion as AccordionPrimitive } from 'radix-ui'
import * as React from 'react'

function Accordion({ className, ...props }: React.ComponentProps<typeof AccordionPrimitive.Root>) {
    return (
        <AccordionPrimitive.Root
            data-slot="accordion"
            className={cn('flex w-full flex-col', className)}
            {...props}
        />
    )
}

function AccordionItem({
    className,
    ...props
}: React.ComponentProps<typeof AccordionPrimitive.Item>) {
    return (
        <AccordionPrimitive.Item
            data-slot="accordion-item"
            className={cn('border-b border-border last:border-b-0', className)}
            {...props}
        />
    )
}

function AccordionTrigger({
    className,
    children,
    ...props
}: React.ComponentProps<typeof AccordionPrimitive.Trigger>) {
    return (
        <AccordionPrimitive.Header className="flex">
            <AccordionPrimitive.Trigger
                data-slot="accordion-trigger"
                className={cn(
                    'group/accordion-trigger flex min-h-12 flex-1 items-center justify-between gap-3 rounded-lg py-3 text-left text-base font-semibold transition-colors outline-none hover:text-pink-ink disabled:pointer-events-none disabled:opacity-50',
                    className
                )}
                {...props}
            >
                {children}
                <ChevronDownIcon className="pointer-events-none size-4 shrink-0 text-muted-foreground transition-transform duration-200 group-data-[state=open]/accordion-trigger:rotate-180 motion-reduce:transition-none" />
            </AccordionPrimitive.Trigger>
        </AccordionPrimitive.Header>
    )
}

function AccordionContent({
    className,
    children,
    ...props
}: React.ComponentProps<typeof AccordionPrimitive.Content>) {
    return (
        <AccordionPrimitive.Content
            data-slot="accordion-content"
            className="overflow-hidden text-sm"
            {...props}
        >
            <div className={cn('pt-1 pb-5', className)}>{children}</div>
        </AccordionPrimitive.Content>
    )
}

export { Accordion, AccordionContent, AccordionItem, AccordionTrigger }
