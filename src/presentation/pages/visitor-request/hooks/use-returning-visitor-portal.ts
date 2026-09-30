import { useCallback, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { ApiError } from '../../../../data/api/api-error'
import type { VisitorPortalMe } from '../../../../domain/entities/visitor-portal-schema'

const PAGE_SIZE = 20

export type ReturningVisitorPortalStatus =
  | 'idle'
  | 'loading'
  | 'loaded'
  | 'unauthorized'
  | 'rate-limited'
  | 'misconfigured'
  | 'error'

export function useReturningVisitorPortal() {
  const { getVisitorPortalMeUseCase } = useAppDependencies()

  const [status, setStatus] = useState<ReturningVisitorPortalStatus>('idle')
  const [data, setData] = useState<VisitorPortalMe | undefined>(undefined)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [proofToken, setProofToken] = useState<string | undefined>(undefined)

  const fetchPage = useCallback(
    async (token: string, page: number) => {
      setStatus('loading')
      setErrorMessage(undefined)
      try {
        const result = await getVisitorPortalMeUseCase.execute(token, { page, pageSize: PAGE_SIZE })
        setData((previous) =>
          page > 1 && previous ? { ...result, history: [...previous.history, ...result.history] } : result,
        )
        setStatus('loaded')
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.status === 401) {
            setStatus('unauthorized')
            return
          }
          if (err.status === 429) {
            setStatus('rate-limited')
            setErrorMessage(err.message)
            return
          }
          if (err.status === 404) {
            setStatus('misconfigured')
            setErrorMessage(err.message)
            return
          }
        }
        setStatus('error')
        setErrorMessage(err instanceof Error ? err.message : 'Something went wrong loading your visit history.')
      }
    },
    [getVisitorPortalMeUseCase],
  )

  // Entry point once OTP verification hands back a proof token.
  const load = useCallback(
    (token: string) => {
      setProofToken(token)
      void fetchPage(token, 1)
    },
    [fetchPage],
  )

  const loadMore = useCallback(() => {
    if (!proofToken || !data) return
    void fetchPage(proofToken, data.pagination.page + 1)
  }, [proofToken, data, fetchPage])

  // Retries the lookup itself (429/404) without re-verifying — the OTP
  // session and its proof token are still valid.
  const retry = useCallback(() => {
    if (!proofToken) return
    void fetchPage(proofToken, data?.pagination.page ?? 1)
  }, [proofToken, data, fetchPage])

  const hasMore = data ? data.pagination.page < data.pagination.totalPages : false

  return { status, data, errorMessage, load, loadMore, retry, hasMore }
}
