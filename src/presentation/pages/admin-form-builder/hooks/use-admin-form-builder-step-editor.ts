import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePolling } from '../../../hooks/use-polling'
import { usePageRefresh } from '../../../context/refresh-context'
import type {
  FormField,
  FormFieldCreateInput,
  FormFieldGroup,
  FormFieldGroupCreateInput,
  FormFieldGroupUpdateInput,
  FormFieldUpdateInput,
  FormStep,
} from '../../../../domain/entities/form-builder-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import { useFormBuilderPublishState } from './use-form-builder-publish-state'

export function useAdminFormBuilderStepEditor() {
  const navigate = useNavigate()
  const { stepId } = useParams<{ stepId: string }>()
  const [searchParams] = useSearchParams()
  const branchId = searchParams.get('branchId') ?? undefined

  const {
    getCurrentStaffUserUseCase,
    listFormStepsUseCase,
    listFormFieldsUseCase,
    createFormFieldUseCase,
    updateFormFieldUseCase,
    deleteFormFieldUseCase,
    reorderFormFieldsUseCase,
    listFormFieldGroupsUseCase,
    createFormFieldGroupUseCase,
    updateFormFieldGroupUseCase,
    deleteFormFieldGroupUseCase,
    reorderFormFieldGroupsUseCase,
    publishFormConfigUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [step, setStep] = useState<FormStep | undefined>(undefined)
  const [fields, setFields] = useState<FormField[]>([])
  const [groups, setGroups] = useState<FormFieldGroup[]>([])
  const [selectedFieldId, setSelectedFieldId] = useState<string | undefined>(undefined)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | undefined>(undefined)
  const [isAddFieldOpen, setIsAddFieldOpen] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<FormField | undefined>(undefined)
  const [isAddGroupOpen, setIsAddGroupOpen] = useState(false)
  const [pendingDeleteGroup, setPendingDeleteGroup] = useState<FormFieldGroup | undefined>(undefined)
  const [isPublishing, setIsPublishing] = useState(false)
  const { hasUnpublishedChanges, markDirty, markPublished } = useFormBuilderPublishState(branchId)

  const load = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!stepId) return
      const silent = options?.silent ?? false

      if (!silent) {
        setIsLoading(true)
        setErrorMessage(undefined)
      }
      try {
        const [steps, stepFields, stepGroups] = await Promise.all([
          listFormStepsUseCase.execute(branchId),
          listFormFieldsUseCase.execute(stepId, branchId),
          listFormFieldGroupsUseCase.execute(stepId, branchId),
        ])
        const foundStep = steps.find((s) => s.id === stepId)
        setStep(foundStep)
        const sortedFields = [...stepFields].sort((a, b) => a.orderIndex - b.orderIndex)
        setFields(sortedFields)
        setGroups([...stepGroups].sort((a, b) => a.orderIndex - b.orderIndex))
        setSelectedFieldId((current) => current ?? sortedFields[0]?.id)
        setLastUpdatedAt(new Date())
      } catch {
        if (!silent) {
          setErrorMessage('Something went wrong loading this step. Please try again.')
        }
        toast.error('Something went wrong loading this step. Please try again.')
      } finally {
        if (!silent) {
          setIsLoading(false)
        }
      }
    },
    [stepId, branchId, listFormStepsUseCase, listFormFieldsUseCase, listFormFieldGroupsUseCase, toast],
  )

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }
    void getCurrentStaffUserUseCase.execute().then(setCurrentUser)
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigate, stepId, branchId])

  const retry = useCallback(() => void load(), [load])

  // Auto-refreshes step fields every 15s; skipped while an add/delete/publish
  // action is in progress (same convention as use-admin-form-builder.ts).
  const isActionInProgress =
    isAddFieldOpen || pendingDelete !== undefined || isAddGroupOpen || pendingDeleteGroup !== undefined || isPublishing
  usePolling(() => void load({ silent: true }), { intervalMs: 15_000, isBusy: isActionInProgress })

  usePageRefresh({ refresh: retry, isRefreshing: isLoading, lastUpdatedAt })

  const selectField = useCallback((fieldId: string) => setSelectedFieldId(fieldId), [])

  const toggleFieldRequired = useCallback(
    async (field: FormField) => {
      if (field.isLocked) return
      try {
        const updated = await updateFormFieldUseCase.execute(field.id, { isRequired: !field.isRequired }, branchId)
        setFields((current) => current.map((f) => (f.id === updated.id ? updated : f)))
        markDirty()
      } catch {
        toast.error('Something went wrong updating the field. Please try again.')
      }
    },
    [updateFormFieldUseCase, branchId, toast, markDirty],
  )

  // Returns `undefined` on success, or the backend's rejection message on
  // failure (e.g. "must declare a non-empty options list") — the caller
  // (`FieldPropertiesPanel`) awaits this to surface that message inline and
  // revert any local draft it optimistically applied, rather than treating
  // this as fire-and-forget the way `toggleFieldRequired`/`createField` do.
  const saveFieldProperties = useCallback(
    async (fieldId: string, input: FormFieldUpdateInput): Promise<string | undefined> => {
      try {
        const updated = await updateFormFieldUseCase.execute(fieldId, input, branchId)
        setFields((current) => current.map((f) => (f.id === updated.id ? updated : f)))
        markDirty()
        toast.success('Field properties saved to draft. Publish to update the visitor form.')
        return undefined
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : 'Something went wrong saving this field. Please check for a conflicting conditional rule.'
        toast.error(message)
        return message
      }
    },
    [updateFormFieldUseCase, branchId, toast, markDirty],
  )

  // Assigns (or clears, via `groupId: null`) a field's group from the row's
  // own group-select dropdown (add-repeatable-field-groups) — a lighter-weight
  // sibling of `saveFieldProperties` that only ever touches `groupId`, so it
  // doesn't need the full properties-panel save flow.
  const assignFieldGroup = useCallback(
    async (fieldId: string, groupId: string | null) => {
      try {
        const updated = await updateFormFieldUseCase.execute(fieldId, { groupId }, branchId)
        setFields((current) => current.map((f) => (f.id === updated.id ? updated : f)))
        markDirty()
      } catch {
        toast.error('Something went wrong assigning this field to a group. Please try again.')
      }
    },
    [updateFormFieldUseCase, branchId, toast, markDirty],
  )

  const requestDeleteField = useCallback((field: FormField) => setPendingDelete(field), [])
  const cancelDeleteField = useCallback(() => setPendingDelete(undefined), [])

  const confirmDeleteField = useCallback(async () => {
    if (!pendingDelete) return
    try {
      await deleteFormFieldUseCase.execute(pendingDelete.id, branchId)
      setFields((current) => current.filter((f) => f.id !== pendingDelete.id))
      setSelectedFieldId((current) => (current === pendingDelete.id ? undefined : current))
      markDirty()
      toast.success('Field removed from draft. Publish to update the visitor form.')
    } catch {
      toast.error('Something went wrong removing the field. Please try again.')
    } finally {
      setPendingDelete(undefined)
    }
  }, [pendingDelete, deleteFormFieldUseCase, branchId, toast, markDirty])

  const openAddField = useCallback(() => setIsAddFieldOpen(true), [])
  const closeAddField = useCallback(() => setIsAddFieldOpen(false), [])

  // Returns `undefined` on success, or the backend's rejection message on
  // failure (e.g. a duplicate field key on this step) — same convention as
  // `saveFieldProperties`. `AddFieldModal` awaits this so it can keep the
  // modal open with the user's input intact and show the real reason inline,
  // instead of silently resetting the form on every click (which made a
  // failed create look identical to a successful one, and invited an
  // accidental duplicate re-submission — see AddFieldModal.tsx).
  const createField = useCallback(
    async (input: FormFieldCreateInput): Promise<string | undefined> => {
      if (!stepId) return undefined
      try {
        const created = await createFormFieldUseCase.execute(stepId, input, branchId)
        setFields((current) => [...current, created].sort((a, b) => a.orderIndex - b.orderIndex))
        setSelectedFieldId(created.id)
        markDirty()
        toast.success('Field created in draft. Publish to update the visitor form.')
        setIsAddFieldOpen(false)
        return undefined
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Something went wrong creating the field. Please try again.'
        toast.error(message)
        return message
      }
    },
    [stepId, createFormFieldUseCase, branchId, toast, markDirty],
  )

  const reorderFields = useCallback(
    async (orderedIds: string[]) => {
      if (!stepId) return
      const previous = fields
      const reordered = orderedIds
        .map((id) => fields.find((f) => f.id === id))
        .filter((f): f is FormField => f !== undefined)
      setFields(reordered)
      try {
        const updated = await reorderFormFieldsUseCase.execute(stepId, orderedIds, branchId)
        setFields([...updated].sort((a, b) => a.orderIndex - b.orderIndex))
        markDirty()
      } catch {
        setFields(previous)
        toast.error('Something went wrong reordering fields. Please try again.')
      }
    },
    [stepId, fields, reorderFormFieldsUseCase, branchId, toast, markDirty],
  )

  const openAddGroup = useCallback(() => setIsAddGroupOpen(true), [])
  const closeAddGroup = useCallback(() => setIsAddGroupOpen(false), [])

  const createGroup = useCallback(
    async (input: FormFieldGroupCreateInput) => {
      if (!stepId) return
      try {
        const created = await createFormFieldGroupUseCase.execute(stepId, input, branchId)
        setGroups((current) => [...current, created].sort((a, b) => a.orderIndex - b.orderIndex))
        markDirty()
        toast.success('Group created in draft. Publish to update the visitor form.')
        setIsAddGroupOpen(false)
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Something went wrong creating the group. Please try again.')
      }
    },
    [stepId, createFormFieldGroupUseCase, branchId, toast, markDirty],
  )

  // Same success/failure-message contract as `saveFieldProperties` — the
  // caller (a group's properties UI) awaits this to surface a backend
  // rejection (e.g. "minInstances must not be greater than maxInstances")
  // inline instead of treating the save as fire-and-forget.
  const saveGroupProperties = useCallback(
    async (groupId: string, input: FormFieldGroupUpdateInput): Promise<string | undefined> => {
      try {
        const updated = await updateFormFieldGroupUseCase.execute(groupId, input, branchId)
        setGroups((current) => current.map((g) => (g.id === updated.id ? updated : g)))
        markDirty()
        toast.success('Group properties saved to draft. Publish to update the visitor form.')
        return undefined
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Something went wrong saving this group. Please try again.'
        toast.error(message)
        return message
      }
    },
    [updateFormFieldGroupUseCase, branchId, toast, markDirty],
  )

  const requestDeleteGroup = useCallback((group: FormFieldGroup) => setPendingDeleteGroup(group), [])
  const cancelDeleteGroup = useCallback(() => setPendingDeleteGroup(undefined), [])

  const confirmDeleteGroup = useCallback(async () => {
    if (!pendingDeleteGroup) return
    try {
      await deleteFormFieldGroupUseCase.execute(pendingDeleteGroup.id, branchId)
      setGroups((current) => current.filter((g) => g.id !== pendingDeleteGroup.id))
      // The group's fields are ungrouped server-side on delete
      // (`form_builder/service.py::delete_group`) — reflect that locally
      // rather than waiting on the next poll tick.
      setFields((current) => current.map((f) => (f.groupId === pendingDeleteGroup.id ? { ...f, groupId: null } : f)))
      markDirty()
      toast.success('Group removed. Its fields are now ungrouped.')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Something went wrong removing the group. Please try again.')
    } finally {
      setPendingDeleteGroup(undefined)
    }
  }, [pendingDeleteGroup, deleteFormFieldGroupUseCase, branchId, toast, markDirty])

  const reorderGroups = useCallback(
    async (orderedIds: string[]) => {
      if (!stepId) return
      const previous = groups
      const reordered = orderedIds
        .map((id) => groups.find((g) => g.id === id))
        .filter((g): g is FormFieldGroup => g !== undefined)
      setGroups(reordered)
      try {
        const updated = await reorderFormFieldGroupsUseCase.execute(stepId, orderedIds, branchId)
        setGroups([...updated].sort((a, b) => a.orderIndex - b.orderIndex))
        markDirty()
      } catch {
        setGroups(previous)
        toast.error('Something went wrong reordering groups. Please try again.')
      }
    },
    [stepId, groups, reorderFormFieldGroupsUseCase, branchId, toast, markDirty],
  )

  const publish = useCallback(async () => {
    setIsPublishing(true)
    try {
      const result = await publishFormConfigUseCase.execute(branchId)
      markPublished()
      toast.success(`Published — now live as v${result.version}.`)
    } catch {
      toast.error('Something went wrong publishing. Please try again.')
    } finally {
      setIsPublishing(false)
    }
  }, [publishFormConfigUseCase, branchId, toast, markPublished])

  const goBack = useCallback(() => navigate('/admin/form-builder'), [navigate])

  const selectedField = fields.find((f) => f.id === selectedFieldId)

  return {
    currentUser,
    step,
    fields,
    groups,
    selectedField,
    selectField,
    isLoading,
    errorMessage,
    retry,
    toggleFieldRequired,
    saveFieldProperties,
    assignFieldGroup,
    pendingDelete,
    requestDeleteField,
    cancelDeleteField,
    confirmDeleteField,
    isAddFieldOpen,
    openAddField,
    closeAddField,
    createField,
    reorderFields,
    isAddGroupOpen,
    openAddGroup,
    closeAddGroup,
    createGroup,
    saveGroupProperties,
    pendingDeleteGroup,
    requestDeleteGroup,
    cancelDeleteGroup,
    confirmDeleteGroup,
    reorderGroups,
    goBack,
    isPublishing,
    publish,
    hasUnpublishedChanges,
  }
}
