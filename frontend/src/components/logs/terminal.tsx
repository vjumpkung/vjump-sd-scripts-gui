import useTheme from '@/hooks/useTheme'
import { FitAddon } from '@xterm/addon-fit'
import { Terminal } from '@xterm/xterm'
import '@xterm/xterm/css/xterm.css'
import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'

export type TerminalHandle = {
    /** Appends text. The log is never re-written, so scrollback and selection survive polling. */
    write: (text: string) => void
    reset: () => void
}

type TerminalComponentProps = {
    label: string
}

const FONT_FAMILY = '"Geist Mono", ui-monospace, Consolas, monospace'

// The terminal follows Code Slate in both themes: Graphite in light, a deeper slate in dark.
const terminalTheme = (dark: boolean) => ({
    background: dark ? '#1f252c' : '#2a313a',
    foreground: '#e0e5ec',
    cursor: '#e0e5ec',
    cursorAccent: dark ? '#1f252c' : '#2a313a',
    selectionBackground: 'rgba(255, 159, 237, 0.35)',
    brightBlack: '#b8c0c9'
})

const TerminalComponent = forwardRef<TerminalHandle, TerminalComponentProps>(({ label }, ref) => {
    const hostRef = useRef<HTMLDivElement>(null)
    const terminalRef = useRef<Terminal | null>(null)
    const dark = useTheme((state) => state.dark)
    const darkRef = useRef(dark)
    darkRef.current = dark

    useImperativeHandle(
        ref,
        () => ({
            write: (text) => terminalRef.current?.write(text),
            reset: () => terminalRef.current?.reset()
        }),
        []
    )

    useEffect(() => {
        const host = hostRef.current
        if (!host) return

        const terminal = new Terminal({
            fontSize: 13,
            lineHeight: 1.4,
            fontFamily: FONT_FAMILY,
            cursorBlink: false,
            convertEol: true,
            scrollback: 20_000,
            theme: terminalTheme(darkRef.current)
        })
        const fit = new FitAddon()
        terminal.loadAddon(fit)
        terminal.open(host)
        terminalRef.current = terminal

        let frame: number | null = null
        const scheduleFit = () => {
            if (frame !== null) return
            frame = requestAnimationFrame(() => {
                frame = null
                if (host.clientWidth === 0 || host.clientHeight === 0) return
                fit.fit()
            })
        }
        const observer = new ResizeObserver(scheduleFit)
        observer.observe(host)
        scheduleFit()

        // The web font loads lazily; measure again once it is ready so columns line up.
        let disposed = false
        void document.fonts?.load('13px "Geist Mono"').then(() => {
            if (disposed) return
            terminal.options.fontFamily = `${FONT_FAMILY}, monospace`
            scheduleFit()
        })

        return () => {
            disposed = true
            observer.disconnect()
            if (frame !== null) cancelAnimationFrame(frame)
            terminalRef.current = null
            // xterm schedules viewport work on the next frame; disposing after that frame avoids
            // a "reading 'dimensions' of undefined" error when the page unmounts right after mount.
            requestAnimationFrame(() => requestAnimationFrame(() => terminal.dispose()))
        }
    }, [])

    useEffect(() => {
        if (terminalRef.current) terminalRef.current.options.theme = terminalTheme(dark)
    }, [dark])

    return (
        <div className="rounded-xl bg-code-bg p-3 dark:border dark:border-border">
            <div
                ref={hostRef}
                role="region"
                aria-label={label}
                translate="no"
                className="h-[55vh] min-h-80"
            />
        </div>
    )
})

TerminalComponent.displayName = 'TerminalComponent'

export default TerminalComponent
