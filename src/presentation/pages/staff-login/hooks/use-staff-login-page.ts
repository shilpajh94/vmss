import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePushNotifications } from '../../../hooks/use-push-notifications'
import { landingPathFor } from '../../../utils/landing-path'

export type StaffLoginStatus = 'idle' | 'submitting' | 'error'

export function useStaffLoginPage() {
  const { loginStaffUseCase, getCurrentStaffUserUseCase, startSsoLoginUseCase } = useAppDependencies()
  const toast = useToast()
  const navigate = useNavigate()
  const { registerCurrentDevice } = usePushNotifications()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [status, setStatus] = useState<StaffLoginStatus>('idle')
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [emailError, setEmailError] = useState<string | undefined>(undefined)
  const [passwordError, setPasswordError] = useState<string | undefined>(undefined)

  const submitLogin = async () => {
    const trimmedEmail = email.trim()
    const trimmedPassword = password.trim()

    setEmailError(trimmedEmail ? undefined : 'Email is required')
    setPasswordError(trimmedPassword ? undefined : 'Password is required')

    if (!trimmedEmail || !trimmedPassword) {
      return
    }

    setStatus('submitting')
    setErrorMessage(undefined)

    try {
      const { token } = await loginStaffUseCase.execute(trimmedEmail, trimmedPassword)
      sessionStorage.setItem('token', token)
      void registerCurrentDevice()

      const user = await getCurrentStaffUserUseCase.execute()
      navigate(landingPathFor(user))
    } catch {
      setErrorMessage('Invalid email or password. Please try again.')
      setStatus('error')
      toast.error('Invalid email or password. Please try again.')
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
