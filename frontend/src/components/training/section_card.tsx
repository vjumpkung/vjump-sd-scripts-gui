import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { ReactNode } from 'react'
import { useId } from 'react'

type SectionCardProps = {
    title: string
    description?: string
    children: ReactNode
    actions?: ReactNode
}

/** A flat Note Card section with a title, as used for every form group. */
const SectionCard = ({ title, description, children, actions }: SectionCardProps) => {
    const titleId = useId()

    return (
        <Card role="group" aria-labelledby={titleId}>
            <CardHeader>
                <div className="flex items-start justify-between gap-3">
                    <CardTitle id={titleId}>{title}</CardTitle>
                    {actions}
                </div>
                {description ? <CardDescription>{description}</CardDescription> : null}
            </CardHeader>
            {children}
        </Card>
    )
}

export const FieldGrid = ({ children }: { children: ReactNode }) => (
    <div className="grid gap-x-6 gap-y-7 md:grid-cols-2">{children}</div>
)

export default SectionCard
