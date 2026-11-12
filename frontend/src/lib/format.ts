const BYTE_UNITS = ['KB', 'MB', 'GB', 'TB'] as const

/** Formats a byte count with a binary scale, e.g. "23.8 GB". */
export const formatBytes = (bytes: number | null | undefined, tag = 'en-US') => {
    if (bytes === null || bytes === undefined || !Number.isFinite(bytes)) return '-'
    if (bytes < 1024) return `${new Intl.NumberFormat(tag).format(bytes)} B`

    let value = bytes / 1024
    let unit: (typeof BYTE_UNITS)[number] = BYTE_UNITS[0]
    for (const next of BYTE_UNITS.slice(1)) {
        if (value < 1024) break
        value /= 1024
        unit = next
    }
    const digits = value >= 100 ? 0 : value >= 10 ? 1 : 2
    return `${new Intl.NumberFormat(tag, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits
    }).format(value)} ${unit}`
}

/** Total size in GB, as used on the download cards. */
export const formatGB = (bytes: number, tag = 'en-US') =>
    `${new Intl.NumberFormat(tag, { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(
        bytes / 1024 ** 3
    )} GB`

export const formatPercent = (value: number | null | undefined, tag = 'en-US', digits = 0) =>
    value === null || value === undefined || !Number.isFinite(value)
        ? '-'
        : `${new Intl.NumberFormat(tag, {
              minimumFractionDigits: digits,
              maximumFractionDigits: digits
          }).format(value)}%`

export const formatDateTime = (value: string | null | undefined, tag = 'en-US') => {
    if (!value) return '-'
    const date = new Date(value)
    return Number.isNaN(date.getTime())
        ? value
        : date.toLocaleString(tag, { dateStyle: 'medium', timeStyle: 'short' })
}

export const formatTime = (value: Date, tag = 'en-US') =>
    value.toLocaleTimeString(tag, { timeStyle: 'medium' })

export const clampPercent = (value: number | null | undefined) =>
    Math.min(100, Math.max(0, value ?? 0))
