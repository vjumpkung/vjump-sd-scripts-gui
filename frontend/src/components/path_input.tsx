import WorkspaceBrowser, { type PathMode } from './workspace_browser'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useSystemStatus } from '@/hooks/useSystem'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'
import { FolderOpenIcon } from 'lucide-react'
import { useState } from 'react'

type PathInputProps = {
    id?: string
    value: string
    onChange: (value: string) => void
    mode?: PathMode
    extensions?: string
    placeholder?: string
    invalid?: boolean
    describedBy?: string
    className?: string
}

/**
 * A path text box with a Browse button. Desktop builds ask the OS through the pywebview bridge
 * (docs/api.md, section 7); the web build lists the workspace through /api/fs/list instead.
 */
const PathInput = ({
    id,
    value,
    onChange,
    mode = 'file',
    extensions,
    placeholder,
    invalid,
    describedBy,
    className
}: PathInputProps) => {
    const { t } = useI18n()
    const status = useSystemStatus()
    const [browsing, setBrowsing] = useState(false)
    const desktopPicker = status.data?.desktop ? window.pywebview?.api?.pick_path : undefined

    const browse = async () => {
        if (!desktopPicker) {
            setBrowsing(true)
            return
        }
        try {
            const picked = await desktopPicker(mode === 'folder' ? 'folder' : 'file', value || null)
            if (picked) onChange(picked)
        } catch {
            // The native dialog failed; offer the workspace browser instead.
            setBrowsing(true)
        }
    }

    return (
        <div className={cn('flex gap-2', className)}>
            <Input
                id={id}
                value={value}
                spellCheck={false}
                autoComplete="off"
                translate="no"
                aria-invalid={invalid || undefined}
                aria-describedby={describedBy}
                placeholder={placeholder}
                className="font-mono"
                onChange={(event) => onChange(event.target.value)}
            />
            <Button
                variant="outline"
                size="icon"
                className="h-11 w-11 shrink-0 rounded-lg"
                aria-label={t('field.browse')}
                title={t('field.browse')}
                onClick={() => void browse()}
            >
                <FolderOpenIcon />
            </Button>
            {browsing ? (
                <WorkspaceBrowser
                    mode={mode}
                    extensions={extensions}
                    initialValue={value}
                    onClose={() => setBrowsing(false)}
                    onSelect={(path) => {
                        onChange(path)
                        setBrowsing(false)
                    }}
                />
            ) : null}
        </div>
    )
}

export default PathInput
