import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePushNotifications } from '../../../hooks/use-push-notifications'
import { postSignInPath, rememberSsoReturnPath, takeSsoReturnPath } from '../../../utils/return-path'
import { loginErrorMessage } from '../../../utils/login-error-message'

export type StaffSsoLoginStatus = 'idle' | 'redirecting' | 'completing' | 'error'

export function useStaffSsoLoginPage() {
  const { startSsoLoginUseCase, exchangeSsoCodeUseCase, getCurrentStaffUserUseCase } = useAppDependencies()
  const toast = useToast()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { refreshRegistrationIfGranted } = usePushNotifications()

  const [status, setStatus] = useState<StaffSsoLoginStatus>('idle')
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const completeSignIn = useCallback(
    async (code: string) => {
      setStatus('completing')
      setErrorMessage(undefined)

      try {
        const { token } = await exchangeSsoCodeUseCase.execute(code)
        sessionStorage.setItem('token', token)
        void refreshRegistrationIfGranted()
        const user = await getCurrentStaffUserUseCase.execute()
        navigate(postSignInPath(user, takeSsoReturnPath(), window.location.origin))
      } catch (error) {
        const message = loginErrorMessage(error, 'Sign-in could not be completed. Please try again.')
        setErrorMessage(message)
        setStatus('error')
        toast.error(message)
      }
    },
    [exchangeSsoCodeUseCase, getCurrentStaffUserUseCase, navigate, toast, refreshRegistrationIfGranted],
  )

  useEffect(() => {
    const code = searchParams.get('code')
    if (code) {
      void completeSignIn(code)
    }
  }, [searchParams, completeSignIn])

  // Already signed in (and not returning from the identity provider): go
  // straight on instead of offering sign-in again.
  useEffect(() => {
    if (searchParams.get('code') || !sessionStorage.getItem('token')) return
    let cancelled = false
    getCurrentStaffUserUseCase
      .execute()
      .then((user) => {
        if (!cancelled) navigate(postSignInPath(user, searchParams.get('from'), window.location.origin), { replace: true })
      })
      .catch(() => {
        // A dead token is cleared by the API client; the page stays.
      })
    return () => {
      cancelled = true
    }
    // Only on arrival.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const startSso = useCallback(() => {
    setStatus('redirecting')
    setErrorMessage(undefined)
    rememberSsoReturnPath(searchParams.get('from'))
    window.location.assign(startSsoLoginUseCase.execute())
  }, [startSsoLoginUseCase, searchParams])

  return {
    status,
    errorMessage,
    startSso,
  }
}
