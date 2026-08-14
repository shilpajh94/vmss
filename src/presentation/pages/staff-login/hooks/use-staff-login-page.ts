import { useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'

export type StaffSsoStatus = 'idle' | 'initiating' | 'error'

export function useStaffLoginPage() {
  const { initiateStaffSsoUseCase } = useAppDependencies()

  const [status, setStatus] = useState<StaffSsoStatus>('idle')
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const signInWithSso = async () => {
    setStatus('initiating')
    setErrorMessage(undefined)

    try {
      const { redirectUrl } = await initiateStaffSsoUseCase.execute()
      window.location.assign(redirectUrl)
    } catch {
      setErrorMessage('Something went wrong starting SSO sign-in. Please try again.')
      setStatus('error')
    }
  }

  return {
    status,
    errorMessage,
    signInWithSso,
  }
}
