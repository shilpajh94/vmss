import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Zone } from '../../domain/entities/zone-schema'
import { fetchAllPages } from '../../data/api/fetch-all-pages'
import { useToast } from '../components/toast/toast-context'
import { useAppDependencies } from '../context/app-dependencies-context'
import { toUserMessage } from '../utils/to-user-message'

// What a zone set belongs to. A category's defaults span branches; a visit's
// zones must all be in the visit's branch, and fall back to its category's.
export type ZoneSetScope =
  | { kind: 'category'; id: string }
  | { kind: 'invitation'; id: string; branchId?: string; categoryId?: string }

const ZONE_PAGE_SIZE = 100

/** Loads the zones a user can pick from plus the saved set, and saves the whole set back (PUT replaces it). */
export function useZoneSet(scope: ZoneSetScope, enabled: boolean) {
  const {
    listZonesUseCase,
    listBranchesUseCase,
    getCategoryZonesUseCase,
    setCategoryZonesUseCase,
    getInvitationZonesUseCase,
    setInvitationZonesUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const [zones, setZones] = useState<Zone[]>([])
  const [branchNames, setBranchNames] = useState<Map<string, string>>(new Map())
  const [savedIds, setSavedIds] = useState<string[]>([])
  const [categoryIds, setCategoryIds] = useState<string[]>([])
  const [draft, setDraft] = useState<string[]>([])
  const [phase, setPhase] = useState<'loading' | 'ready' | 'error'>('loading')
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | undefined>(undefined)

  const scopeKey = scope.kind === 'category' ? `category:${scope.id}` : `invitation:${scope.id}:${scope.branchId ?? ''}:${scope.categoryId ?? ''}`
  const isCategory = scope.kind === 'category'
  const branchId = scope.kind === 'invitation' ? scope.branchId : undefined
  const categoryId = scope.kind === 'invitation' ? scope.categoryId : undefined
  const scopeId = scope.id

  const load = useCallback(async () => {
    setPhase('loading')
    try {
      const [zoneList, ids, branches] = await Promise.all([
        fetchAllPages((page, pageSize) => listZonesUseCase.execute({ page, pageSize, branchId, sortBy: 'name', sortOrder: 'asc' }), { pageSize: ZONE_PAGE_SIZE }),
        isCategory ? getCategoryZonesUseCase.execute(scopeId) : getInvitationZonesUseCase.execute(scopeId),
        isCategory ? listBranchesUseCase.execute() : Promise.resolve([]),
      ])
      // Category fallback is display-only; a failure to read it must not block editing the visit's own set.
      const fallbackIds = !isCategory && ids.length === 0 && categoryId ? await getCategoryZonesUseCase.execute(categoryId).catch(() => []) : []
      setZones(zoneList)
      setBranchNames(new Map(branches.map((branch) => [branch.id, branch.name])))
      setSavedIds(ids)
      setCategoryIds(fallbackIds)
      setDraft(ids)
      setSaveError(undefined)
      setPhase('ready')
    } catch {
      setPhase('error')
    }
  }, [listZonesUseCase, listBranchesUseCase, getCategoryZonesUseCase, getInvitationZonesUseCase, isCategory, scopeId, branchId, categoryId])

  useEffect(() => {
    if (!enabled) return
    void load()
    // `scopeKey` restarts the load when the visit or category changes.
  }, [enabled, load, scopeKey])

  const toggle = useCallback((zoneId: string, checked: boolean) => {
    setDraft((current) => (checked ? [...current, zoneId] : current.filter((existing) => existing !== zoneId)))
  }, [])

  const save = useCallback(async (): Promise<boolean> => {
    setIsSaving(true)
    setSaveError(undefined)
    try {
      if (isCategory) await setCategoryZonesUseCase.execute(scopeId, draft)
      else await setInvitationZonesUseCase.execute(scopeId, draft)
      toast.success(draft.length === 0 && !isCategory ? 'Zones cleared. Category defaults now apply.' : 'Zones saved.')
      await load()
      return true
    } catch (error) {
      // A 422 (zone outside the visit's branch) lands here; the selection stays as the user left it.
      setSaveError(toUserMessage(error, 'Something went wrong saving the zones. Please try again.'))
      return false
    } finally {
      setIsSaving(false)
    }
  }, [isCategory, scopeId, draft, setCategoryZonesUseCase, setInvitationZonesUseCase, toast, load])

  const isDirty = useMemo(() => {
    if (draft.length !== savedIds.length) return true
    const saved = new Set(savedIds)
    return draft.some((id) => !saved.has(id))
  }, [draft, savedIds])

  const usingCategoryDefaults = !isCategory && savedIds.length === 0 && categoryIds.length > 0
  const effectiveIds = savedIds.length > 0 ? savedIds : categoryIds

  return {
    zones,
    branchNames,
    savedIds,
    categoryIds,
    effectiveIds,
    usingCategoryDefaults,
    // Nothing mapped on the visit or its category (or on the category itself): the backend denies every zone.
    deniesEverything: effectiveIds.length === 0,
    draft,
    isDirty,
    phase,
    isSaving,
    saveError,
    toggle,
    clear: useCallback(() => setDraft([]), []),
    save,
    retry: load,
  }
}
