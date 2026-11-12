import { mutationKeys } from '../api/api'
import { useIsMutating } from '@tanstack/react-query'
import { useEffect } from 'react'

const useManagedUploadGuard = () => {
    const uploading = useIsMutating({ mutationKey: mutationKeys.managedUpload }) > 0

    useEffect(() => {
        if (!uploading) return

        const warnBeforeUnload = (event: BeforeUnloadEvent) => {
            event.preventDefault()
            event.returnValue = true
        }

        window.addEventListener('beforeunload', warnBeforeUnload)
        return () => window.removeEventListener('beforeunload', warnBeforeUnload)
    }, [uploading])

    return uploading
}

export default useManagedUploadGuard
