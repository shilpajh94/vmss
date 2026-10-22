import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { LIVE_REFRESH_INTERVAL_MS, usePolling } from '../../../hooks/use-polling'
import { usePageRefresh } from '../../../context/refresh-context'
import { useLoadTracker, type LoadMode } from '../../../hooks/use-load-tracker'
import type { FormStep } from '../../../../domain/entities/form-builder-schema'
import type { Branch } from '../../../../domain/entities/branch-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import { useFormBuilderPublishState } from './use-form-builder-publish-state'
import { toUserMessage } from '../../../utils/to-user-message'
import { slugifyKey } from '../form-builder-key'

/** Sentinel used in the workspace `<select>` for the tenant-wide default
 * scope — `undefined` (a real branch id otherwise) is what every
 * form-builder use-case actually expects.
 */
export const DEFAULT_WORKSPACE_VALUE = ''

export function useAdminFormBuilder() {
  const navigate = useNavigate()
  const {
    getCurrentStaffUserUseCase,
    listBranchesUseCase,
    listFormStepsUseCase,
    createFormStepUseCase,
    updateFormStepUseCase,
    deleteFormStepUseCase,
    reorderFormStepsUseCase,
    publishFormConfigUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [branches, setBranches] = useState<Branch[]>([])
  const [selectedBranchId, setSelectedBranchId] = useState<string | undefined>(undefined)
  const [steps, setSteps] = useState<FormStep[]>([])
  const { phase, isRefreshing, begin } = useLoadTracker()
  const [isPublishing, setIsPublishing] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<FormStep | undefined>(undefined)
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const { hasUnpublishedChanges, markDirty, markPublished } = useFormBuilderPublishState(selectedBranchId)

  const loadBranches = useCallback(async () => {
    try {
      const list = await listBranchesUseCase.execute()
      setBranches(list)
    } catch {
      // Non-fatal: the workspace selector just shows the default scope only.
    }
  }, [listBranchesUseCase])

  const loadSteps = useCallback(
    async (branchId: string | undefined, mode: LoadMode = 'user') => {
      const request = begin(mode)

      try {
        const list = await listFormStepsUseCase.execute(branchId)
        if (!request.succeed()) return
        setSteps([...list].sort((a, b) => a.orderIndex - b.orderIndex))
      } catch {
        if (!request.fail()) return
        toast.error('Something went wrong loading the registration steps. Please try again.')
      }
    },
    [begin, listFormStepsUseCase, toast],
  )

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }
    void getCurrentStaffUserUseCase.execute().then(setCurrentUser)
    void loadBranches()
    void loadSteps(undefined)
    // Runs once on mount — selectedBranchId changes are handled by selectWorkspace below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigate])

  const selectWorkspace = useCallback(
    (value: string) => {
      const branchId = value === DEFAULT_WORKSPACE_VALUE ? undefined : value
      setSelectedBranchId(branchId)
      void loadSteps(branchId)
    },
    [loadSteps],
  )

  const retry = useCallback(() => {
    void loadSteps(selectedBranchId)
  }, [loadSteps, selectedBranchId])

  // Auto-refreshes steps every 15s; skipped while a create/delete/publish
  // action is in progress so a background tick can't replace data underneath
  // an in-progress user action (same convention as use-admin-branches.ts).
  const isActionInProgress = isCreateOpen || pendingDelete !== undefined || isPublishing
  usePolling(() => void loadSteps(selectedBranchId, 'background'), { intervalMs: LIVE_REFRESH_INTERVAL_MS, isBusy: isActionInProgress })

  usePageRefresh({ refresh: retry, isRefreshing: phase === 'initial' || isRefreshing })

  const toggleStepActive = useCallback(
    async (step: FormStep) => {
      try {
        const updated = await updateFormStepUseCase.execute(step.id, { isActive: !step.isActive }, selectedBranchId)
        setSteps((current) => current.map((s) => (s.id === updated.id ? updated : s)))
        markDirty()
      } catch (error) {
        toast.error(
          step.isLocked
            ? 'This step is locked and cannot be deactivated.'
            : toUserMessage(error, 'Something went wrong updating the step. Please try again.'),
        )
      }
    },
    [updateFormStepUseCase, selectedBranchId, toast, markDirty],
  )

  const requestDeleteStep = useCallback((step: FormStep) => setPendingDelete(step), [])
  const cancelDeleteStep = useCallback(() => setPendingDelete(undefined), [])

  const confirmDeleteStep = useCallback(async () => {
    if (!pendingDelete) return
    try {
      await deleteFormStepUseCase.execute(pendingDelete.id, selectedBranchId)
      setSteps((current) => current.filter((s) => s.id !== pendingDelete.id))
      markDirty()
      toast.success('Step removed.')
    } catch (error) {
      toast.error(toUserMessage(error, 'Something went wrong removing the step. Please try again.'))
    } finally {
      setPendingDelete(undefined)
    }
  }, [pendingDelete, deleteFormStepUseCase, selectedBranchId, toast, markDirty])

  const openCreateStep = useCallback(() => setIsCreateOpen(true), [])
  const closeCreateStep = useCallback(() => setIsCreateOpen(false), [])

  const createStep = useCallback(
    async (name: string): Promise<string | undefined> => {
      try {
        const created = await createFormStepUseCase.execute({ key: slugifyKey(name), name: name.trim() }, selectedBranchId)
        setSteps((current) => [...current, created].sort((a, b) => a.orderIndex - b.orderIndex))
        markDirty()
        toast.success('Registration step created.')
        setIsCreateOpen(false)
        return undefined
      } catch (error) {
        const message = toUserMessage(error, 'Something went wrong creating the step. Please try again.')
        toast.error(message)
        return message
      }
    },
    [createFormStepUseCase, selectedBranchId, toast, markDirty],
  )

  const reorderSteps = useCallback(
    async (orderedIds: string[]) => {
      const previous = steps
      const reordered = orderedIds
        .map((id) => steps.find((s) => s.id === id))
        .filter((s): s is FormStep => s !== undefined)
      setSteps(reordered)
      try {
        const updated = await reorderFormStepsUseCase.execute(orderedIds, selectedBranchId)
        setSteps([...updated].sort((a, b) => a.orderIndex - b.orderIndex))
        markDirty()
      } catch (error) {
        setSteps(previous)
        toast.error(toUserMessage(error, 'Something went wrong reordering steps. Please try again.'))
      }
    },
    [steps, reorderFormStepsUseCase, selectedBranchId, toast, markDirty],
  )

  const goToEditFields = useCallback(
    (step: FormStep) => {
      const query = selectedBranchId ? `?branchId=${selectedBranchId}` : ''
      navigate(`/admin/form-builder/steps/${step.id}${query}`)
    },
    [navigate, selectedBranchId],
  )

  const publish = useCallback(async () => {
    setIsPublishing(true)
    try {
      const result = await publishFormConfigUseCase.execute(selectedBranchId)
      markPublished()
      toast.success(`Published — now live as v${result.version}.`)
    } catch (error) {
      toast.error(toUserMessage(error, 'Something went wrong publishing. Please try again.'))
    } finally {
      setIsPublishing(false)
    }
  }, [publishFormConfigUseCase, selectedBranchId, toast, markPublished])

  return {
    currentUser,
    branches,
    selectedBranchId,
    selectWorkspace,
    steps,
    phase,
    isRefreshing,
    retry,
    toggleStepActive,
    pendingDelete,
    requestDeleteStep,
    cancelDeleteStep,
    confirmDeleteStep,
    isCreateOpen,
    openCreateStep,
    closeCreateStep,
    createStep,
    reorderSteps,
    goToEditFields,
    isPublishing,
    publish,
    hasUnpublishedChanges,
  }
}
