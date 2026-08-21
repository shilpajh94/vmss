import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'

export type StaffLoginStatus = 'idle' | 'submitting' | 'error'

export function useStaffLoginPage() {
  const { loginStaffUseCase, getCurrentStaffUserUseCase } = useAppDependencies()
  const toast = useToast()
  const navigate = useNavigate()

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

      const user = await getCurrentStaffUserUseCase.execute()
      navigate(user.isAdmin ? '/admin/dashboard' : '/staff/dashboard')
    } catch {
      setErrorMessage('Invalid email or password. Please try again.')
      setStatus('error')
      toast.error('Invalid email or password. Please try again.')
    }
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
  }
}
