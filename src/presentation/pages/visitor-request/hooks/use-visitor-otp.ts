import { useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { isValidEmail } from '../../../utils/is-valid-email'
import { isValidPhoneNumber } from '../../../utils/is-valid-phone-number'
import type { RegistrationType } from '../types'

export type OtpPhase = 'request' | 'verify'
export type OtpRequestStatus = 'idle' | 'requesting' | 'requested' | 'error'
export type OtpVerifyStatus = 'idle' | 'verifying' | 'error'

interface UseVisitorOtpOptions {
  onVerified: (registrationType: RegistrationType, contact: string, proofToken: string) => void
}

export function useVisitorOtp({ onVerified }: UseVisitorOtpOptions) {
  const { requestVisitorOtpUseCase, verifyVisitorOtpUseCase } = useAppDependencies()
  const toast = useToast()

  const [phase, setPhase] = useState<OtpPhase>('request')
  const [registrationType, setRegistrationType] = useState<RegistrationType>('individual')
  const [contact, setContact] = useState('')
  const [contactError, setContactError] = useState<string | undefined>(undefined)
  const [requestStatus, setRequestStatus] = useState<OtpRequestStatus>('idle')
  const [requestErrorMessage, setRequestErrorMessage] = useState<string | undefined>(undefined)

  const [code, setCode] = useState('')
  const [codeError, setCodeError] = useState<string | undefined>(undefined)
  const [verifyStatus, setVerifyStatus] = useState<OtpVerifyStatus>('idle')
  const [verifyErrorMessage, setVerifyErrorMessage] = useState<string | undefined>(undefined)

  const requestOtp = async () => {
    const trimmedContact = contact.trim()

    if (!trimmedContact) {
      setContactError('Mobile number or email is required.')
      return
    }

    const looksLikeEmail = trimmedContact.includes('@')
    const isValid = looksLikeEmail ? isValidEmail(trimmedContact) : isValidPhoneNumber(trimmedContact)
    if (!isValid) {
      setContactError(looksLikeEmail ? 'Enter a valid email address.' : 'Enter a valid mobile number.')
      return
    }

    setContactError(undefined)
    setRequestStatus('requesting')
    setRequestErrorMessage(undefined)

    try {
      await requestVisitorOtpUseCase.execute({ registrationType, contact: trimmedContact })
      setRequestStatus('requested')
      setPhase('verify')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Something went wrong requesting a code. Please try again.'
      setRequestErrorMessage(message)
      setRequestStatus('error')
      toast.error(message)
    }
  }

  const verifyOtp = async () => {
    if (!code.trim()) {
      setCodeError('Verification code is required.')
      return
    }

    setCodeError(undefined)
    setVerifyStatus('verifying')
    setVerifyErrorMessage(undefined)

    try {
      const response = await verifyVisitorOtpUseCase.execute({ contact: contact.trim(), code: code.trim() })
      setVerifyStatus('idle')
      toast.success('Contact verified.')
      onVerified(registrationType, contact.trim(), response.data.proofToken)
    } catch {
      setVerifyErrorMessage('That code is invalid or has expired. Please try again.')
      setVerifyStatus('error')
      toast.error('That code is invalid or has expired. Please try again.')
    }
  }

  const useDifferentContact = () => {
    setPhase('request')
    setContact('')
    setContactError(undefined)
    setRequestStatus('idle')
    setRequestErrorMessage(undefined)
    setCode('')
    setCodeError(undefined)
    setVerifyStatus('idle')
    setVerifyErrorMessage(undefined)
  }

  return {
    phase,
    registrationType,
    setRegistrationType,
    contact,
    setContact,
    contactError,
    requestStatus,
    requestErrorMessage,
    requestOtp,
    code,
    setCode,
    codeError,
    verifyStatus,
    verifyErrorMessage,
    verifyOtp,
    useDifferentContact,
  }
}
