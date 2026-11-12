import axios from 'axios'

export const API_BASE_URL = String(import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export const apiClient = axios.create({
    baseURL: API_BASE_URL,
    timeout: 180_000,
    headers: {
        Accept: 'application/json'
    }
})

export const apiUrl = (path: string) => `${API_BASE_URL}${path}`

type ValidationItem = { loc?: Array<string | number>; msg?: string }

const describeDetail = (detail: unknown): string | null => {
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail)) {
        // FastAPI's own 422 shape for malformed bodies.
        const parts = (detail as ValidationItem[])
            .map((item) => {
                if (!item || typeof item.msg !== 'string') return null
                const where = (item.loc ?? []).filter((part) => part !== 'body').join('.')
                return where ? `${where}: ${item.msg}` : item.msg
            })
            .filter((part): part is string => Boolean(part))
        if (parts.length) return parts.join('; ')
    }
    return null
}

/**
 * Turns any thrown value into a human readable message. `fallback` is a localized sentence the
 * caller supplies, so this module stays free of UI strings.
 */
export const getApiErrorMessage = (error: unknown, fallback: string) => {
    if (!axios.isAxiosError(error)) return error instanceof Error ? error.message : fallback

    const detail = describeDetail(error.response?.data?.detail)
    if (detail) return detail
    if (error.code === 'ECONNABORTED') return `${fallback} (timeout)`
    if (error.code === 'ERR_CANCELED') return `${fallback} (cancelled)`
    if (!error.response) return `${fallback} (${error.message})`

    return `${fallback} (HTTP ${error.response.status})`
}

export const httpStatus = (error: unknown): number | null =>
    axios.isAxiosError(error) ? (error.response?.status ?? null) : null
