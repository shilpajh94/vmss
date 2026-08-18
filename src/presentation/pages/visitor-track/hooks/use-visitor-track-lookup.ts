import { useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { TrackingLookupResponse } from '../../../../domain/entities/tracking-lookup-response-schema'

export type LookupStatus = 'idle' | 'loading' | 'success' | 'error'

export function useVisitorTrackLookup() {
  const { trackVisitRequestUseCase } = useAppDependencies()
  const toast = useToast()

  const [trackingId, setTrackingId] = useState('')
  const [validationError, setValidationError] = useState<string | undefined>(undefined)
  const [status, setStatus] = useState<LookupStatus>('idle')
  const [response, setResponse] = useState<TrackingLookupResponse | undefined>(undefined)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const submit = async () => {
    if (!trackingId.trim()) {
      setValidationError('Tracking ID is required.')
      return
    }

    setValidationError(undefined)
    setStatus('loading')
    setErrorMessage(undefined)

    try {
      const result = await trackVisitRequestUseCase.execute(trackingId.trim())
      setResponse(result)
      setStatus('success')
    } catch {
      setErrorMessage("We couldn't find a request with that tracking ID. Please check and try again.")
      setStatus('error')
      toast.error("We couldn't find a request with that tracking ID. Please check and try again.")
    }
  }

  return {
    trackingId,
    setTrackingId,
    validationError,
    status,
    response,
    errorMessage,
    submit,
  }
}
