import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePushNotifications } from '../../../hooks/use-push-notifications'
import { landingPathFor } from '../../../utils/landing-path'
import { loginErrorMessage } from '../../../utils/login-error-message'

export type StaffLoginStatus = 'idle' | 'submitting' | 'error'

export function useStaffLoginPage() {
  const { loginStaffUseCase, getCurrentStaffUserUseCase, startSsoLoginUseCase } = useAppDependencies()
  const toast = useToast()
  const navigate = useNavigate()
  const { refreshRegistrationIfGranted } = usePushNotifications()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [status, setStatus] = useState<StaffLoginStatus>('idle')
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [emailError, setEmailError] = useState<string | undefined>(undefined)
  const [passwordError, setPasswordError] = useState<string | undefined>(undefined)

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
      navigate(landingPathFor(user))
    } catch (error) {
      const message = loginErrorMessage(error, 'Invalid email or password. Please try again.')
      setErrorMessage(message)
      setStatus('error')
      toast.error(message)
    }
  }

  const startSso = () => {
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
