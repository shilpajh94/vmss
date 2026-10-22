import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePushNotifications } from '../../../hooks/use-push-notifications'
import { postSignInPath, rememberSsoReturnPath } from '../../../utils/return-path'
import { loginErrorMessage } from '../../../utils/login-error-message'

export type StaffLoginStatus = 'idle' | 'submitting' | 'error'

export function useStaffLoginPage() {
  const { loginStaffUseCase, getCurrentStaffUserUseCase, startSsoLoginUseCase } = useAppDependencies()
  const toast = useToast()
  const navigate = useNavigate()
  const { refreshRegistrationIfGranted } = usePushNotifications()
  const [searchParams] = useSearchParams()
  // The page that sent the user here (`?from=`), validated on use.
  const from = searchParams.get('from')

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [status, setStatus] = useState<StaffLoginStatus>('idle')
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [emailError, setEmailError] = useState<string | undefined>(undefined)
  const [passwordError, setPasswordError] = useState<string | undefined>(undefined)

  // Already signed in: go straight on instead of showing the form again.
  useEffect(() => {
    if (!sessionStorage.getItem('token')) return
    let cancelled = false
    getCurrentStaffUserUseCase
      .execute()
      .then((user) => {
        if (!cancelled) navigate(postSignInPath(user, from, window.location.origin), { replace: true })
      })
      .catch(() => {
        // A dead token is cleared by the API client; the form stays.
      })
    return () => {
      cancelled = true
    }
    // Only on arrival: a sign-in from this page navigates itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const submitLogin = async () => {
    // The password is sent exactly as typed: spaces can be part of it.
    const trimmedEmail = email.trim()

    setEmailError(trimmedEmail ? undefined : 'Email is required')
    setPasswordError(password ? undefined : 'Password is required')

    if (!trimmedEmail || !password) {
      return
    }

    setStatus('submitting')
    setErrorMessage(undefined)

    try {
      const { token } = await loginStaffUseCase.execute(trimmedEmail, password)
      sessionStorage.setItem('token', token)
      void refreshRegistrationIfGranted()

      const user = await getCurrentStaffUserUseCase.execute()
      navigate(postSignInPath(user, from, window.location.origin))
    } catch (error) {
      const message = loginErrorMessage(error, 'Invalid email or password. Please try again.')
      setErrorMessage(message)
      setStatus('error')
      toast.error(message)
    }
  }

  const startSso = () => {
    rememberSsoReturnPath(from)
    window.location.assign(startSsoLoginUseCase.execute())
  }

  return {
    email,
    password,
    setEmail,
    setPassword,
    status,
    errorMessage,
    emailError,
    passwordError,
    submitLogin,
    startSso,
  }
}
