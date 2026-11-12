import { type Dict, en } from './en'
import { th } from './th'
import { useMemo } from 'react'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Locale = 'en' | 'th'
export type I18nKey = keyof Dict
export type Vars = Record<string, string | number>

const dictionaries: Record<Locale, Dict> = { en, th }

const detectLocale = (): Locale =>
    typeof navigator !== 'undefined' && (navigator.language ?? '').toLowerCase().startsWith('th')
        ? 'th'
        : 'en'

type LocaleState = {
    locale: Locale
    setLocale: (locale: Locale) => void
}

export const useLocale = create<LocaleState>()(
    persist(
        (set) => ({
            locale: detectLocale(),
            setLocale: (locale) => set({ locale })
        }),
        { name: 'sdgui:locale', version: 1 }
    )
)

// `{count#item|items}` picks the singular when vars.count is 1 and the plural otherwise.
// `{name}` inserts a value. Thai has no plural forms, so its strings use plain `{count}`.
const interpolate = (template: string, vars?: Vars) =>
    vars
        ? template
              .replace(
                  /\{(\w+)#([^|}]*)\|([^}]*)\}/g,
                  (match, name: string, one: string, other: string) =>
                      name in vars ? (Number(vars[name]) === 1 ? one : other) : match
              )
              .replace(/\{(\w+)\}/g, (match, name: string) =>
                  name in vars ? String(vars[name]) : match
              )
        : template

export const translate = (locale: Locale, key: I18nKey, vars?: Vars) =>
    interpolate(dictionaries[locale][key] ?? dictionaries.en[key] ?? key, vars)

/** Looks up a key built at run time, such as `fields.<dest>.label`. Undefined when absent. */
export const lookup = (locale: Locale, key: string, vars?: Vars) => {
    const dictionary = dictionaries[locale] as Record<string, string>
    const fallback = dictionaries.en as Record<string, string>
    const value = dictionary[key] ?? fallback[key]
    return value === undefined ? undefined : interpolate(value, vars)
}

/** Browser locale tag used for number and date formatting. */
export const localeTag = (locale: Locale) => (locale === 'th' ? 'th-TH-u-ca-gregory' : 'en-US')

export const useI18n = () => {
    const locale = useLocale((state) => state.locale)
    const setLocale = useLocale((state) => state.setLocale)

    // Stable between renders for one locale so memoized children are not re-rendered needlessly.
    return useMemo(
        () => ({
            locale,
            setLocale,
            tag: localeTag(locale),
            t: (key: I18nKey, vars?: Vars) => translate(locale, key, vars),
            lookup: (key: string, vars?: Vars) => lookup(locale, key, vars)
        }),
        [locale, setLocale]
    )
}

/** Mirrors the locale onto <html lang>. Call once, before the first render. */
export const initLocale = () => {
    const apply = (locale: Locale) => {
        document.documentElement.lang = locale
    }

    apply(useLocale.getState().locale)
    useLocale.subscribe((state, previous) => {
        if (state.locale !== previous.locale) apply(state.locale)
    })
}
