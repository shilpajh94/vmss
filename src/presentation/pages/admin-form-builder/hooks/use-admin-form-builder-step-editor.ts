import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePolling } from '../../../hooks/use-polling'
import { usePageRefresh } from '../../../context/refresh-context'
import type {
  FormField,
  FormFieldCreateInput,
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
    publishFormConfigUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [step, setStep] = useState<FormStep | undefined>(undefined)
  const [fields, setFields] = useState<FormField[]>([])
  const [selectedFieldId, setSelectedFieldId] = useState<string | undefined>(undefined)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | undefined>(undefined)
  const [isAddFieldOpen, setIsAddFieldOpen] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<FormField | undefined>(undefined)
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
        const [steps, stepFields] = await Promise.all([
          listFormStepsUseCase.execute(branchId),
          listFormFieldsUseCase.execute(stepId, branchId),
        ])
        const foundStep = steps.find((s) => s.id === stepId)
        setStep(foundStep)
        const sortedFields = [...stepFields].sort((a, b) => a.orderIndex - b.orderIndex)
        setFields(sortedFields)
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
    [stepId, branchId, listFormStepsUseCase, listFormFieldsUseCase, toast],
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
  const isActionInProgress = isAddFieldOpen || pendingDelete !== undefined || isPublishing
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

  const saveFieldProperties = useCallback(
    async (fieldId: string, input: FormFieldUpdateInput) => {
      try {
        const updated = await updateFormFieldUseCase.execute(fieldId, input, branchId)
        setFields((current) => current.map((f) => (f.id === updated.id ? updated : f)))
        markDirty()
        toast.success('Field properties saved to draft. Publish to update the visitor form.')
      } catch {
        toast.error('Something went wrong saving this field. Please check for a conflicting conditional rule.')
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

  const createField = useCallback(
    async (input: FormFieldCreateInput) => {
      if (!stepId) return
      try {
        const created = await createFormFieldUseCase.execute(stepId, input, branchId)
        setFields((current) => [...current, created].sort((a, b) => a.orderIndex - b.orderIndex))
        setSelectedFieldId(created.id)
        markDirty()
        toast.success('Field created in draft. Publish to update the visitor form.')
        setIsAddFieldOpen(false)
      } catch {
        toast.error('Something went wrong creating the field. Please try again.')
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
    selectedField,
    selectField,
    isLoading,
    errorMessage,
    retry,
    toggleFieldRequired,
    saveFieldProperties,
    pendingDelete,
    requestDeleteField,
    cancelDeleteField,
    confirmDeleteField,
    isAddFieldOpen,
    openAddField,
    closeAddField,
    createField,
    reorderFields,
    goBack,
    isPublishing,
    publish,
    hasUnpublishedChanges,
  }
}
