import { Button } from '@/components/ui/button'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'
import { CheckIcon, CopyIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

export const copyText = async (text: string) => {
    try {
        await navigator.clipboard.writeText(text)
        return true
    } catch {
        // Fall back to a hidden textarea for non-secure origins (plain http on a remote pod).
        const area = document.createElement('textarea')
        area.value = text
        area.setAttribute('readonly', '')
        area.style.position = 'fixed'
        area.style.opacity = '0'
        document.body.appendChild(area)
        area.select()
        try {
            return document.execCommand('copy')
        } catch {
            return false
        } finally {
            area.remove()
        }
    }
}

type CopyButtonProps = {
    text: string
    label: string
    className?: string
}

// The 32px copy button is the one documented exception to the 40px target rule: it sits in a
// code block (DESIGN.md, Do's).
export const CopyButton = ({ text, label, className }: CopyButtonProps) => {
    const { t } = useI18n()
    const [status, setStatus] = useState<'idle' | 'copied' | 'failed'>('idle')
    const timer = useRef<number | undefined>(undefined)

    useEffect(() => () => window.clearTimeout(timer.current), [])

    const copy = async () => {
        setStatus((await copyText(text)) ? 'copied' : 'failed')
        window.clearTimeout(timer.current)
        timer.current = window.setTimeout(() => setStatus('idle'), 1_800)
    }

    return (
        <>
            <Button
                variant="ghost"
                size="icon-sm"
                aria-label={label}
                title={label}
                disabled={!text}
                className={cn(
                    'border border-white/15 bg-white/10 text-code-fg hover:bg-brand-yellow hover:text-ink focus-visible:opacity-100 [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover/code:opacity-100',
                    status !== 'idle' && '[@media(hover:hover)]:opacity-100',
                    className
                )}
                onClick={() => void copy()}
            >
                {status === 'copied' ? <CheckIcon /> : <CopyIcon />}
            </Button>
            <span className="sr-only" role="status" aria-live="polite">
                {status === 'copied'
                    ? t('common.copied')
                    : status === 'failed'
                      ? t('common.copyFailed')
                      : ''}
            </span>
        </>
    )
}

type CodeBlockProps = {
    code: string
    copyLabel: string
    placeholder?: string
    className?: string
}

/** Code Slate block with a copy button (DESIGN.md, Code Block). Stays dark in both themes. */
export const CodeBlock = ({ code, copyLabel, placeholder, className }: CodeBlockProps) => (
    <div
        className={cn(
            'group/code relative rounded-xl bg-code-bg text-code-fg dark:border dark:border-border',
            className
        )}
    >
        <pre
            tabIndex={0}
            translate="no"
            className="code-scroll max-h-[480px] overflow-auto p-4 pr-12 font-mono text-[0.8125rem] leading-[1.7] break-all whitespace-pre-wrap"
        >
            {code || <span className="opacity-60">{placeholder}</span>}
        </pre>
        <CopyButton text={code} label={copyLabel} className="absolute top-2 right-2" />
    </div>
)
