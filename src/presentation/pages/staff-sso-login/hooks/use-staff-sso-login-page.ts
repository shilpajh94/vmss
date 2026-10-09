import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePushNotifications } from '../../../hooks/use-push-notifications'

export type StaffSsoLoginStatus = 'idle' | 'redirecting' | 'completing' | 'error'

export function useStaffSsoLoginPage() {
  const { startSsoLoginUseCase, exchangeSsoCodeUseCase, getCurrentStaffUserUseCase } = useAppDependencies()
  const toast = useToast()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { registerCurrentDevice } = usePushNotifications()

  const [status, setStatus] = useState<StaffSsoLoginStatus>('idle')
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const completeSignIn = useCallback(
    async (code: string) => {
      setStatus('completing')
      setErrorMessage(undefined)

      try {
        const { token } = await exchangeSsoCodeUseCase.execute(code)
        sessionStorage.setItem('token', token)
        void registerCurrentDevice()
        const user = await getCurrentStaffUserUseCase.execute()
        navigate(user.isAdmin ? '/admin/dashboard' : '/staff/dashboard')
      } catch {
        setErrorMessage('Sign-in could not be completed. Please try again.')
        setStatus('error')
        toast.error('Sign-in could not be completed. Please try again.')
      }
    },
    [exchangeSsoCodeUseCase, getCurrentStaffUserUseCase, navigate, toast, registerCurrentDevice],
  )

  useEffect(() => {
    const code = searchParams.get('code')
    if (code) {
      void completeSignIn(code)
    }
  }, [searchParams, completeSignIn])

  const startSso = useCallback(() => {
    setStatus('redirecting')
    setErrorMessage(undefined)
    window.location.assign(startSsoLoginUseCase.execute())
  }, [startSsoLoginUseCase])

  return {
    status,
    errorMessage,
    startSso,
  }
}
