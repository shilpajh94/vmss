import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { ApiError } from '../../../../data/api/api-error'
import type { CheckinSearchRow } from '../../../../domain/entities/checkin-schema'
import { describePrintError, isFeatureOff } from '../../../utils/badge-print-errors'

const PAGE_SIZE = 20
export const REASON_MAX = 255

export function useBadgePrinting() {
  const { searchCheckinVisitsUseCase, uploadCheckinPhotoUseCase, verifyCheckinIdUseCase, printVisitorBadgeUseCase, reprintVisitorBadgeUseCase } = useAppDependencies()
  const toast = useToast()

  const [draft, setDraft] = useState('')
  const [query, setQuery] = useState<string | undefined>(undefined)
  const [page, setPage] = useState(1)
  const [rows, setRows] = useState<CheckinSearchRow[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | undefined>(undefined)
  const [isUnavailable, setIsUnavailable] = useState(false)
  const [busyId, setBusyId] = useState<string | undefined>(undefined)
  const [pdfLink, setPdfLink] = useState<string | undefined>(undefined)
  const [reprintTarget, setReprintTarget] = useState<CheckinSearchRow | undefined>(undefined)
  const [reason, setReason] = useState('')

  const requestRef = useRef(0)

  const load = useCallback(
    async (q: string, targetPage: number) => {
      const request = ++requestRef.current
      setIsLoading(true)
      setLoadError(undefined)
      try {
        const result = await searchCheckinVisitsUseCase.execute({ q, page: targetPage, pageSize: PAGE_SIZE })
        if (request !== requestRef.current) return
        setRows(result.items)
        setTotal(result.total)
      } catch (error) {
        if (request !== requestRef.current) return
        if (isFeatureOff(error)) setIsUnavailable(true)
        else setLoadError(error instanceof ApiError ? error.message : 'Something went wrong searching. Please try again.')
      } finally {
        if (request === requestRef.current) setIsLoading(false)
      }
    },
    [searchCheckinVisitsUseCase],
  )

  useEffect(() => {
    if (query !== undefined) void load(query, page)
  }, [query, page, load])

  // Revoke the object URL behind the fallback link when it is replaced or the page unmounts.
  useEffect(() => () => {
    if (pdfLink) URL.revokeObjectURL(pdfLink)
  }, [pdfLink])

  const submitSearch = useCallback(
    (event: FormEvent) => {
      event.preventDefault()
      const q = draft.trim()
      if (!q) return
      setPdfLink(undefined)
      if (q === query && page === 1) void load(q, 1)
      setQuery(q)
      setPage(1)
    },
    [draft, query, page, load],
  )

  const openPdf = useCallback((blob: Blob) => {
    const url = URL.createObjectURL(blob)
    const opened = window.open(url, '_blank')
    if (opened) {
      // Revoked later: the new tab needs the URL while it loads the PDF.
      window.setTimeout(() => URL.revokeObjectURL(url), 5 * 60_000)
      setPdfLink(undefined)
    } else {
      setPdfLink(url)
    }
  }, [])

  const refreshRows = useCallback(() => (query !== undefined ? load(query, page) : Promise.resolve()), [query, page, load])

  const verifyId = useCallback(
    async (row: CheckinSearchRow) => {
      setBusyId(row.id)
      try {
        await verifyCheckinIdUseCase.execute(row.id)
        toast.success(`ID verified for ${row.fullName}.`)
        await refreshRows()
      } catch (error) {
        if (isFeatureOff(error)) setIsUnavailable(true)
        else toast.error(error instanceof ApiError ? error.message : 'Could not verify the ID. Please try again.')
      } finally {
        setBusyId(undefined)
      }
    },
    [verifyCheckinIdUseCase, toast, refreshRows],
  )

  const printBadge = useCallback(
    async (row: CheckinSearchRow) => {
      setBusyId(row.id)
      try {
        openPdf(await printVisitorBadgeUseCase.execute(row.id))
        toast.success(`Badge printed for ${row.fullName}.`)
        await refreshRows()
      } catch (error) {
        if (isFeatureOff(error)) {
          setIsUnavailable(true)
          return
        }
        toast.error(describePrintError(error, 'print'))
      } finally {
        setBusyId(undefined)
      }
    },
    [printVisitorBadgeUseCase, openPdf, toast, refreshRows],
  )

  const uploadPhoto = useCallback(
    async (row: CheckinSearchRow, file: File) => {
      setBusyId(row.id)
      try {
        await uploadCheckinPhotoUseCase.execute(row.id, file)
        toast.success(`Photo saved for ${row.fullName}.`)
        await refreshRows()
      } catch (error) {
        if (isFeatureOff(error)) setIsUnavailable(true)
        else if (error instanceof ApiError && error.status === 409) {
          toast.info('This visit already has a photo.')
          await refreshRows()
        } else toast.error(error instanceof ApiError ? error.message : 'Could not upload the photo. Please try again.')
      } finally {
        setBusyId(undefined)
      }
    },
    [uploadCheckinPhotoUseCase, toast, refreshRows],
  )

  const startReprint = useCallback((row: CheckinSearchRow) => {
    setReason('')
    setReprintTarget(row)
  }, [])

  const cancelReprint = useCallback(() => setReprintTarget(undefined), [])

  const trimmedReason = reason.trim()
  const reasonValid = trimmedReason.length >= 1 && trimmedReason.length <= REASON_MAX

  // Only ever reached from the confirm dialog's button: reprint is a GET that
  // invalidates the previous badge, so nothing else may call it.
  const confirmReprint = useCallback(async () => {
    if (!reprintTarget || !reasonValid) return
    setBusyId(reprintTarget.id)
    try {
      openPdf(await reprintVisitorBadgeUseCase.execute(reprintTarget.id, trimmedReason))
      toast.success(`Badge reprinted for ${reprintTarget.fullName}. The previous badge no longer works.`)
      setReprintTarget(undefined)
      await refreshRows()
    } catch (error) {
      if (isFeatureOff(error)) {
        setReprintTarget(undefined)
        setIsUnavailable(true)
      } else toast.error(describePrintError(error, 'reprint'))
    } finally {
      setBusyId(undefined)
    }
  }, [reprintTarget, reasonValid, trimmedReason, reprintVisitorBadgeUseCase, openPdf, toast, refreshRows])

  return {
    draft,
    setDraft,
    submitSearch,
    hasSearched: query !== undefined,
    page,
    pageSize: PAGE_SIZE,
    total,
    prevPage: () => setPage((value) => Math.max(1, value - 1)),
    nextPage: () => setPage((value) => value + 1),
    rows,
    isLoading,
    loadError,
    retry: refreshRows,
    isUnavailable,
    busyId,
    pdfLink,
    verifyId,
    uploadPhoto,
    printBadge,
    reprintTarget,
    reason,
    setReason,
    reasonValid,
    startReprint,
    cancelReprint,
    confirmReprint,
  }
}
