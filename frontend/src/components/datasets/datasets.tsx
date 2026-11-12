import DatasetConfigs from './dataset_configs'
import ImageFolders from './image_folders'
import PageHeader from '@/components/page_header'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import useManagedUploadGuard from '@/hooks/useManagedUploadGuard'
import { useI18n } from '@/i18n'
import { useState } from 'react'

type DatasetTab = 'configs' | 'folders'

const Datasets = () => {
    const { t } = useI18n()
    const [tab, setTab] = useState<DatasetTab>('configs')
    // Leaving the folders tab would drop an upload's progress, so the tabs lock while one runs.
    const uploading = useManagedUploadGuard()

    return (
        <div>
            <PageHeader
                before={t('datasets.title.before')}
                mark={t('datasets.title.mark')}
                description={t('datasets.subtitle')}
            />
            <Tabs
                value={tab}
                onValueChange={(next) => setTab(next as DatasetTab)}
                className="gap-6"
            >
                <TabsList aria-label={t('datasets.title.mark')}>
                    <TabsTrigger value="configs" disabled={uploading}>
                        {t('datasets.tab.configs')}
                    </TabsTrigger>
                    <TabsTrigger value="folders" disabled={uploading}>
                        {t('datasets.tab.folders')}
                    </TabsTrigger>
                </TabsList>
            </Tabs>
            <div className="mt-6">{tab === 'configs' ? <DatasetConfigs /> : <ImageFolders />}</div>
        </div>
    )
}

export default Datasets
