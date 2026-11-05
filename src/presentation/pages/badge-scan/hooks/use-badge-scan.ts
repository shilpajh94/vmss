import { useCallback, useState } from 'react'
import { useSearchParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { ApiError } from '../../../../data/api/api-error'
import type { BadgeScanResult } from '../../../../domain/entities/checkin-schema'
import { isFeatureOff, isIdNotVerifiedError } from '../../../utils/badge-print-errors'

export type ScanAction = 'check-in' | 'check-out' | 're-enter'

export type ScanOutcome =
  | { kind: 'success'; action: ScanAction; result: BadgeScanResult }
  | { kind: 'error'; message: string }
  | { kind: 'id-required' }
  | { kind: 'unavailable' }

function describeScanError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 400) return 'This badge is not valid. It may be for another day, replaced by a reprint, tampered with, or already used.'
    if (error.status === 429) return 'Scanning too fast. Please wait a moment and try again.'
    return error.message
  }
  return 'Something went wrong. Please try again.'
}

// Public page: the QR token is the credential. It is only prefilled from
// `?token=`, never submitted automatically, never retried, and never stored.
export function useBadgeScan() {
  const { checkInWithBadgeUseCase, checkOutWithBadgeUseCase, reEnterWithBadgeUseCase } = useAppDependencies()
  const [searchParams] = useSearchParams()
  const [token, setToken] = useState(() => searchParams.get('token') ?? '')
  const [pending, setPending] = useState<ScanAction | undefined>(undefined)
  const [outcome, setOutcome] = useState<ScanOutcome | undefined>(undefined)

  const submit = useCallback(
    async (action: ScanAction) => {
      const value = token.trim()
      if (!value || pending) return
      setPending(action)
      setOutcome(undefined)
      try {
        const useCase =
          action === 'check-in' ? checkInWithBadgeUseCase : action === 'check-out' ? checkOutWithBadgeUseCase : reEnterWithBadgeUseCase
        setOutcome({ kind: 'success', action, result: await useCase.execute(value) })
        setToken('')
      } catch (error) {
        // Verification is a staff attestation and this page has no staff session or visit id,
        // so the visitor is sent to reception rather than offered a Verify ID action.
        setOutcome(
          isFeatureOff(error)
            ? { kind: 'unavailable' }
            : action === 'check-in' && isIdNotVerifiedError(error)
              ? { kind: 'id-required' }
              : { kind: 'error', message: describeScanError(error) },
        )
      } finally {
        setPending(undefined)
      }
    },
    [token, pending, checkInWithBadgeUseCase, checkOutWithBadgeUseCase, reEnterWithBadgeUseCase],
  )

  return { token, setToken, pending, outcome, checkIn: () => submit('check-in'), checkOut: () => submit('check-out'), reEnter: () => submit('re-enter') }
}
