import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useI18n } from '@/i18n'
import { PlusIcon, XIcon } from 'lucide-react'

type KeyValueEditorProps = {
    id: string
    items: string[]
    onChange: (items: string[]) => void
    describedBy?: string
}

const splitItem = (item: string) => {
    const index = item.indexOf('=')
    return index === -1
        ? { key: item, value: '' }
        : { key: item.slice(0, index), value: item.slice(index + 1) }
}

// A row with no value is stored as the bare key, so a half-typed row never ends with a dangling "=".
const joinItem = (key: string, value: string) => (value === '' ? key : `${key}=${value}`)

/** Rows of key=value pairs for list args such as network_args and optimizer_args. */
const KeyValueEditor = ({ id, items, onChange, describedBy }: KeyValueEditorProps) => {
    const { t } = useI18n()

    const update = (index: number, key: string, value: string) =>
        onChange(items.map((item, at) => (at === index ? joinItem(key, value) : item)))

    return (
        <div className="flex flex-col gap-2" role="group" aria-describedby={describedBy}>
            {items.length === 0 ? (
                <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
                    {t('kv.empty')}
                </p>
            ) : (
                items.map((item, index) => {
                    const { key, value } = splitItem(item)
                    return (
                        <div key={index} className="flex items-center gap-2">
                            <Input
                                id={index === 0 ? id : undefined}
                                value={key}
                                placeholder={t('kv.key')}
                                aria-label={`${t('kv.key')} ${index + 1}`}
                                spellCheck={false}
                                autoComplete="off"
                                translate="no"
                                className="min-w-0 flex-[2] font-mono"
                                onChange={(event) =>
                                    update(index, event.target.value.replace(/=/g, ''), value)
                                }
                            />
                            <span aria-hidden className="text-muted-foreground">
                                =
                            </span>
                            <Input
                                value={value}
                                placeholder={t('kv.value')}
                                aria-label={`${t('kv.value')} ${index + 1}`}
                                spellCheck={false}
                                autoComplete="off"
                                translate="no"
                                className="min-w-0 flex-[3] font-mono"
                                onChange={(event) => update(index, key, event.target.value)}
                            />
                            <Button
                                variant="ghost"
                                size="icon"
                                aria-label={t('kv.remove')}
                                title={t('kv.remove')}
                                onClick={() => onChange(items.filter((_, at) => at !== index))}
                            >
                                <XIcon />
                            </Button>
                        </div>
                    )
                })
            )}
            <div>
                <Button variant="outline" onClick={() => onChange([...items, ''])}>
                    <PlusIcon />
                    {t('kv.add')}
                </Button>
            </div>
        </div>
    )
}

export default KeyValueEditor
