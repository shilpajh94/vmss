import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useCurrentUser } from '../../../context/current-user-context'
import { useToast } from '../../../components/toast/toast-context'
import { useLiveResource } from '../../../hooks/use-live-resource'
import type { FormStep } from '../../../../domain/entities/form-builder-schema'
import type { Branch } from '../../../../domain/entities/branch-schema'
import { useFormBuilderPublishState } from './use-form-builder-publish-state'
import { toUserMessage } from '../../../utils/to-user-message'
import { slugifyKey } from '../form-builder-key'

/** Sentinel used in the workspace `<select>` for the tenant-wide default
 * scope — `undefined` (a real branch id otherwise) is what every
 * form-builder use-case actually expects.
 */
export const DEFAULT_WORKSPACE_VALUE = ''

const EMPTY_STEPS: FormStep[] = []
const EMPTY_BRANCHES: Branch[] = []

export function useAdminFormBuilder() {
  const navigate = useNavigate()
  const {
    listBranchesUseCase,
    listFormStepsUseCase,
    createFormStepUseCase,
    updateFormStepUseCase,
    deleteFormStepUseCase,
    reorderFormStepsUseCase,
    publishFormConfigUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const currentUser = useCurrentUser()
  const [selectedBranchId, setSelectedBranchId] = useState<string | undefined>(undefined)
  const [isPublishing, setIsPublishing] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<FormStep | undefined>(undefined)
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const { hasUnpublishedChanges, markDirty, markPublished } = useFormBuilderPublishState(selectedBranchId)

  // The workspace's steps are the live data; the branch list (the workspace
  // selector) loads once, and a failure there just leaves the default scope.
  // Polls skip while a create/delete/publish is in progress.
  const isActionInProgress = isCreateOpen || pendingDelete !== undefined || isPublishing
  const resource = useLiveResource({
    load: async () => [...(await listFormStepsUseCase.execute(selectedBranchId))].sort((a, b) => a.orderIndex - b.orderIndex),
    query: { selectedBranchId },
    reference: () => listBranchesUseCase.execute(),
    errorMessage: 'Something went wrong loading the registration steps. Please try again.',
    isBusy: isActionInProgress,
  })
  const { phase, isRefreshing, retry, setData } = resource
  const steps = resource.data ?? EMPTY_STEPS
  const branches = resource.reference ?? EMPTY_BRANCHES
  const setSteps = useCallback(
    (next: FormStep[] | ((current: FormStep[]) => FormStep[])) =>
      setData((current) => (typeof next === 'function' ? next(current ?? []) : next)),
    [setData],
  )

  const selectWorkspace = useCallback((value: string) => {
    setSelectedBranchId(value === DEFAULT_WORKSPACE_VALUE ? undefined : value)
  }, [])

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
    [updateFormStepUseCase, selectedBranchId, toast, markDirty, setSteps],
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
  }, [pendingDelete, deleteFormStepUseCase, selectedBranchId, toast, markDirty, setSteps])

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
    [createFormStepUseCase, selectedBranchId, toast, markDirty, setSteps],
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
    [steps, reorderFormStepsUseCase, selectedBranchId, toast, markDirty, setSteps],
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
