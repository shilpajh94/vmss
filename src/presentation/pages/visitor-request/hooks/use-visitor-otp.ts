import { useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import type { RegistrationType } from '../types'

export type OtpPhase = 'request' | 'verify'
export type OtpRequestStatus = 'idle' | 'requesting' | 'requested' | 'error'
export type OtpVerifyStatus = 'idle' | 'verifying' | 'error'

interface UseVisitorOtpOptions {
  onVerified: (registrationType: RegistrationType, contact: string) => void
}

export function useVisitorOtp({ onVerified }: UseVisitorOtpOptions) {
  const { requestVisitorOtpUseCase, verifyVisitorOtpUseCase } = useAppDependencies()

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
    if (!contact.trim()) {
      setContactError('Mobile number or email is required.')
      return
    }

    setContactError(undefined)
    setRequestStatus('requesting')
    setRequestErrorMessage(undefined)

    try {
      await requestVisitorOtpUseCase.execute({ registrationType, contact: contact.trim() })
      setRequestStatus('requested')
      setPhase('verify')
    } catch {
      setRequestErrorMessage('Something went wrong requesting a code. Please try again.')
      setRequestStatus('error')
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
      if (!response.verified) {
        setVerifyErrorMessage('That code is invalid or has expired. Please try again.')
        setVerifyStatus('error')
        return
      }
      setVerifyStatus('idle')
      onVerified(registrationType, contact.trim())
    } catch {
      setVerifyErrorMessage('Something went wrong verifying that code. Please try again.')
      setVerifyStatus('error')
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
