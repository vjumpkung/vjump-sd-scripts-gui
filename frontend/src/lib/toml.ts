/*
 * "Additional TOML options" support. The dataset editor offers a textarea of `key = value` lines
 * for sd-scripts options that have no dedicated input. The lines are parsed into JSON values and
 * merged into the config; the backend owns the real TOML rendering.
 */

export type TomlScalar = string | number | boolean
export type TomlValue = TomlScalar | TomlValue[]

const BARE_KEY = /^[A-Za-z0-9_-]+$/
const INTEGER = /^[+-]?\d+$/
const FLOAT = /^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$/

const tomlKey = (key: string) => (BARE_KEY.test(key) ? key : JSON.stringify(key))

/** Renders a JSON value the way it is typed in the textarea. */
export const formatTomlValue = (value: unknown): string => {
    if (typeof value === 'string') return JSON.stringify(value)
    if (typeof value === 'boolean') return value ? 'true' : 'false'
    if (typeof value === 'number' && Number.isFinite(value)) return String(value)
    if (Array.isArray(value)) return `[${value.map(formatTomlValue).join(', ')}]`
    return JSON.stringify(String(value))
}

export const formatAdditionalOptions = (options: Record<string, unknown>) =>
    Object.entries(options)
        .map(([key, value]) => `${tomlKey(key)} = ${formatTomlValue(value)}`)
        .join('\n')

/** Splits an array body on top-level commas, respecting quotes and nested brackets. */
const splitTopLevel = (body: string) => {
    const parts: string[] = []
    let depth = 0
    let quote: string | null = null
    let current = ''

    for (let index = 0; index < body.length; index += 1) {
        const char = body[index]
        if (quote) {
            current += char
            if (char === '\\' && quote === '"') {
                current += body[(index += 1)] ?? ''
            } else if (char === quote) {
                quote = null
            }
            continue
        }
        if (char === '"' || char === "'") {
            quote = char
            current += char
        } else if (char === '[') {
            depth += 1
            current += char
        } else if (char === ']') {
            depth -= 1
            current += char
        } else if (char === ',' && depth === 0) {
            parts.push(current)
            current = ''
        } else {
            current += char
        }
    }
    if (current.trim()) parts.push(current)
    return parts
}

export const parseTomlValue = (raw: string): TomlValue => {
    const value = raw.trim()
    if (value === 'true') return true
    if (value === 'false') return false
    if (INTEGER.test(value)) return Number.parseInt(value, 10)
    if (FLOAT.test(value)) return Number.parseFloat(value)
    if (value.startsWith('"') && value.endsWith('"') && value.length >= 2) {
        try {
            return JSON.parse(value) as string
        } catch {
            return value.slice(1, -1)
        }
    }
    if (value.startsWith("'") && value.endsWith("'") && value.length >= 2) {
        return value.slice(1, -1)
    }
    if (value.startsWith('[') && value.endsWith(']')) {
        return splitTopLevel(value.slice(1, -1)).map(parseTomlValue)
    }
    return value
}

export type AdditionalOptionsResult =
    { ok: true; values: Record<string, TomlValue> } | { ok: false; line: number; text: string }

/**
 * Parses `key = value` lines. Blank lines and `#` comments are skipped. Reports the first line
 * that is not a key/value pair so the editor can point at it.
 */
export const parseAdditionalOptions = (text: string): AdditionalOptionsResult => {
    const values: Record<string, TomlValue> = {}
    const lines = text.split(/\r?\n/)

    for (const [index, rawLine] of lines.entries()) {
        const line = rawLine.trim()
        if (!line || line.startsWith('#')) continue

        const match = /^("(?:[^"\\]|\\.)*"|[A-Za-z0-9_.-]+)\s*=\s*(.*)$/.exec(line)
        if (!match || match[2].trim() === '') return { ok: false, line: index + 1, text: rawLine }

        const key = match[1].startsWith('"') ? (JSON.parse(match[1]) as string) : match[1]
        values[key] = parseTomlValue(match[2])
    }

    return { ok: true, values }
}
