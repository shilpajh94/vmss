import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useCurrentUser } from '../../../context/current-user-context'
import { useToast } from '../../../components/toast/toast-context'
import { LIVE_REFRESH_INTERVAL_MS, usePolling } from '../../../hooks/use-polling'
import { usePageRefresh } from '../../../context/refresh-context'
import { useLoadTracker, type LoadMode } from '../../../hooks/use-load-tracker'
import type {
  FormField,
  FormFieldCreateInput,
  FormFieldGroup,
  FormFieldGroupCreateInput,
  FormFieldGroupUpdateInput,
  FormFieldUpdateInput,
  FormStep,
} from '../../../../domain/entities/form-builder-schema'
import { useFormBuilderPublishState } from './use-form-builder-publish-state'
import { toUserMessage } from '../../../utils/to-user-message'
import { useUnsavedChangesGuard } from '../../../hooks/use-unsaved-changes-guard'

export function useAdminFormBuilderStepEditor() {
  const navigate = useNavigate()
  const { stepId } = useParams<{ stepId: string }>()
  const [searchParams] = useSearchParams()
  const branchId = searchParams.get('branchId') ?? undefined

  const {
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

  const currentUser = useCurrentUser()
  const [step, setStep] = useState<FormStep | undefined>(undefined)
  const [fields, setFields] = useState<FormField[]>([])
  const [groups, setGroups] = useState<FormFieldGroup[]>([])
  const [selectedFieldId, setSelectedFieldId] = useState<string | undefined>(undefined)
  const { phase, isRefreshing, begin } = useLoadTracker()
  const [isAddFieldOpen, setIsAddFieldOpen] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<FormField | undefined>(undefined)
  const [isAddGroupOpen, setIsAddGroupOpen] = useState(false)
  const [pendingDeleteGroup, setPendingDeleteGroup] = useState<FormFieldGroup | undefined>(undefined)
  const [isPublishing, setIsPublishing] = useState(false)
  const { hasUnpublishedChanges, markDirty, markPublished } = useFormBuilderPublishState(branchId)

  const load = useCallback(
    async (mode: LoadMode = 'user') => {
      if (!stepId) return
      const request = begin(mode)

      try {
        const [steps, stepFields, stepGroups] = await Promise.all([
          listFormStepsUseCase.execute(branchId),
          listFormFieldsUseCase.execute(stepId, branchId),
          listFormFieldGroupsUseCase.execute(stepId, branchId),
        ])
        if (!request.succeed()) return
        const foundStep = steps.find((s) => s.id === stepId)
        setStep(foundStep)
        const sortedFields = [...stepFields].sort((a, b) => a.orderIndex - b.orderIndex)
        setFields(sortedFields)
        setGroups([...stepGroups].sort((a, b) => a.orderIndex - b.orderIndex))
        setSelectedFieldId((current) => current ?? sortedFields[0]?.id)
      } catch {
        // A failing poll keeps the last fields without a toast; the next
        // tick retries (live-data-refresh).
        if (!request.fail() || (mode === 'background' && !request.isInitial)) return
        toast.error('Something went wrong loading this step. Please try again.')
      }
    },
    [begin, stepId, branchId, listFormStepsUseCase, listFormFieldsUseCase, listFormFieldGroupsUseCase, toast],
  )

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stepId, branchId])

  const retry = useCallback(() => void load(), [load])

  // Auto-refreshes step fields every 15s; skipped while an add/delete/publish
  // action is in progress (same convention as use-admin-form-builder.ts).
  const isActionInProgress =
    isAddFieldOpen || pendingDelete !== undefined || isAddGroupOpen || pendingDeleteGroup !== undefined || isPublishing
  usePolling(() => void load('background'), { intervalMs: LIVE_REFRESH_INTERVAL_MS, isBusy: isActionInProgress })

  usePageRefresh({ refresh: retry, isRefreshing: phase === 'initial' || isRefreshing })

  // Bumped only on an explicit Edit/select click (not the auto-select on
  // load) so the page can scroll the properties panel into view.
  const [panelScrollRequest, setPanelScrollRequest] = useState(0)
  // The properties panel reports unsaved edits, so switching to another
  // field (or leaving the page) asks before dropping them (D-W6).
  const [isPanelDirty, setIsPanelDirty] = useState(false)
  const { confirmDiscard } = useUnsavedChangesGuard(isPanelDirty)
  const selectField = useCallback(
    (fieldId: string) => {
      const show = () => {
        setSelectedFieldId(fieldId)
        setPanelScrollRequest((n) => n + 1)
      }
      if (fieldId === selectedFieldId) show()
      else confirmDiscard(show)
    },
    [selectedFieldId, confirmDiscard],
  )

  const toggleFieldRequired = useCallback(
    async (field: FormField) => {
      if (field.isLocked) return
      try {
        const updated = await updateFormFieldUseCase.execute(field.id, { isRequired: !field.isRequired }, branchId)
        setFields((current) => current.map((f) => (f.id === updated.id ? updated : f)))
        markDirty()
      } catch (error) {
        toast.error(toUserMessage(error, 'Something went wrong updating the field. Please try again.'))
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
      if (input.fieldType === 'file_upload') {
        const field = fields.find((f) => f.id === fieldId)
        const groupId = field?.groupId
        if (groupId) {
          const groupAlreadyHasFileUpload = fields.some(
            (f) => f.id !== fieldId && f.groupId === groupId && f.fieldType === 'file_upload',
          )
          if (groupAlreadyHasFileUpload) {
            const message = 'This group already has a file upload field. A group can only contain one.'
            toast.error(message)
            return message
          }
        }
      }
      try {
        const updated = await updateFormFieldUseCase.execute(fieldId, input, branchId)
        setFields((current) => current.map((f) => (f.id === updated.id ? updated : f)))
        markDirty()
        toast.success('Field properties saved to draft. Publish to update the visitor form.')
        return undefined
      } catch (error) {
        const message = toUserMessage(error, 'Something went wrong saving this field. Please check for a conflicting conditional rule.')
        toast.error(message)
        return message
      }
    },
    [fields, updateFormFieldUseCase, branchId, toast, markDirty],
  )

  // Assigns (or clears, via `groupId: null`) a field's group from the row's
  // own group-select dropdown (add-repeatable-field-groups) — a lighter-weight
  // sibling of `saveFieldProperties` that only ever touches `groupId`, so it
  // doesn't need the full properties-panel save flow.
  //
  // Only one `file_upload` field per group is ever actually wired end-to-end
  // (frontend's `groupFileFieldKey`/backend's `_group_field_file_key` both
  // only extract the first such field's answer as a real uploaded file) — a
  // second one renders a working-looking control whose file silently never
  // reaches the backend. Blocked here client-side rather than left to a
  // backend rejection, since the backend currently accepts it silently too.
  const assignFieldGroup = useCallback(
    async (fieldId: string, groupId: string | null) => {
      const field = fields.find((f) => f.id === fieldId)
      if (groupId && field?.fieldType === 'file_upload') {
        const groupAlreadyHasFileUpload = fields.some(
          (f) => f.id !== fieldId && f.groupId === groupId && f.fieldType === 'file_upload',
        )
        if (groupAlreadyHasFileUpload) {
          toast.error('This group already has a file upload field. A group can only contain one.')
          return
        }
      }
      try {
        const updated = await updateFormFieldUseCase.execute(fieldId, { groupId }, branchId)
        setFields((current) => current.map((f) => (f.id === updated.id ? updated : f)))
        markDirty()
      } catch (error) {
        toast.error(toUserMessage(error, 'Something went wrong assigning this field to a group. Please try again.'))
      }
    },
    [fields, updateFormFieldUseCase, branchId, toast, markDirty],
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
    } catch (error) {
      toast.error(toUserMessage(error, 'Something went wrong removing the field. Please try again.'))
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
      if (input.groupId && input.fieldType === 'file_upload') {
        const groupAlreadyHasFileUpload = fields.some(
          (f) => f.groupId === input.groupId && f.fieldType === 'file_upload',
        )
        if (groupAlreadyHasFileUpload) {
          const message = 'This group already has a file upload field. A group can only contain one.'
          toast.error(message)
          return message
        }
      }
      try {
        const created = await createFormFieldUseCase.execute(stepId, input, branchId)
        setFields((current) => [...current, created].sort((a, b) => a.orderIndex - b.orderIndex))
        setSelectedFieldId(created.id)
        markDirty()
        toast.success('Field created in draft. Publish to update the visitor form.')
        setIsAddFieldOpen(false)
        return undefined
      } catch (error) {
        const message = toUserMessage(error, 'Something went wrong creating the field. Please try again.')
        toast.error(message)
        return message
      }
    },
    [stepId, fields, createFormFieldUseCase, branchId, toast, markDirty],
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
      } catch (error) {
        setFields(previous)
        toast.error(toUserMessage(error, 'Something went wrong reordering fields. Please try again.'))
      }
    },
    [stepId, fields, reorderFormFieldsUseCase, branchId, toast, markDirty],
  )

  const openAddGroup = useCallback(() => setIsAddGroupOpen(true), [])
  const closeAddGroup = useCallback(() => setIsAddGroupOpen(false), [])

  const createGroup = useCallback(
    async (input: FormFieldGroupCreateInput): Promise<string | undefined> => {
      if (!stepId) return 'This step could not be found.'
      try {
        const created = await createFormFieldGroupUseCase.execute(stepId, input, branchId)
        setGroups((current) => [...current, created].sort((a, b) => a.orderIndex - b.orderIndex))
        markDirty()
        toast.success('Group created in draft. Publish to update the visitor form.')
        setIsAddGroupOpen(false)
        return undefined
      } catch (error) {
        const message = toUserMessage(error, 'Something went wrong creating the group. Please try again.')
        toast.error(message)
        return message
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
        const message = toUserMessage(error, 'Something went wrong saving this group. Please try again.')
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
      toast.error(toUserMessage(error, 'Something went wrong removing the group. Please try again.'))
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
      } catch (error) {
        setGroups(previous)
        toast.error(toUserMessage(error, 'Something went wrong reordering groups. Please try again.'))
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
    } catch (error) {
      toast.error(toUserMessage(error, 'Something went wrong publishing. Please try again.'))
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
    setIsPanelDirty,
    panelScrollRequest,
    phase,
    isRefreshing,
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
