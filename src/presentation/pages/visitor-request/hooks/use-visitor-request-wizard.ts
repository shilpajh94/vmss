import { useEffect, useMemo, useRef, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { findStepFields, useEffectiveForm } from '../../../hooks/use-effective-form'
import { isValidPhoneNumber } from '../../../utils/is-valid-phone-number'
import { todayAsDateInputValue } from '../../../utils/local-date-input-value'
import type { Branch } from '../../../../domain/entities/branch-schema'
import { getActiveSteps, type StepKey } from '../registration-wizard-steps'
import {
  createInitialFormState,
  toVisitRequest,
  type RegistrationType,
  type VisitorFormEntry,
  type VisitRequestFormState,
} from '../types'
import type { SubmissionStatus } from '../Components/steps/ReviewConfirmStep'

export interface VisitorRequestWizardInitialData {
  registrationType?: RegistrationType
  primaryContact?: Partial<Pick<VisitorFormEntry, 'email' | 'phone'>>
}

function buildInitialFormState(initial?: VisitorRequestWizardInitialData): VisitRequestFormState {
  const formState = createInitialFormState()
  if (initial?.registrationType) formState.registrationType = initial.registrationType
  if (initial?.primaryContact) formState.primaryContact = { ...formState.primaryContact, ...initial.primaryContact }
  return formState
}

// `isPrimary` gates the preferred-contact-method-matching rule: the primary
// contact (or the individual visitor) must supply the field matching their
// chosen preferred contact method, while an additional group visitor — who
// has no preferred contact method of their own — just needs at least one of
// email or phone, mirroring the API's `VisitorSubmit`/`_require_reachable_contact`.
function validateVisitorContact(contact: VisitorFormEntry, isPrimary: boolean): Record<string, string> {
  const errors: Record<string, string> = {}
  if (!contact.fullName) errors.fullName = 'Full name is required.'
  if (isPrimary) {
    if (!contact.preferredContactMethod) {
      errors.preferredContactMethod = 'Preferred contact method is required.'
    } else if (contact.preferredContactMethod === 'email' && !contact.email) {
      errors.email = 'Email is required.'
    } else if (contact.preferredContactMethod === 'sms' && !contact.phone) {
      errors.phone = 'Phone number is required.'
    }
  } else if (!contact.email && !contact.phone) {
    errors.email = 'Either email or phone is required.'
  }
  if (contact.phone && !isValidPhoneNumber(contact.phone)) errors.phone = 'Enter a valid phone number.'
  if (!contact.visitorCategory) errors.visitorCategory = 'Visitor category is required.'
  if (!contact.idProofType) errors.idProofType = 'ID proof type is required.'
  if (!contact.idProofFileRef) errors.idProofFileRef = 'ID proof file is required.'
  // Profile image is only collected for the primary contact (VisitorFieldsForm
  // only renders it when showExtendedFields is set, which the additional-visitor
  // draft form disables), so only enforce it there.
  if (isPrimary && !contact.profileImageFileRef) errors.profileImageFileRef = 'Profile image is required.'
  return errors
}

// Keyed by the step's form-builder `key`, not its numeric position — the
// position shifts whenever an earlier step is deactivated or steps are
// reordered, but a given step's validation rule doesn't (design.md
// Decision 3).
function validateStep(
  stepKey: StepKey | string | undefined,
  formState: VisitRequestFormState,
  requiredConsentKeys: string[],
): Record<string, string> {
  if (stepKey === 'visitor_info') {
    const errors = validateVisitorContact(formState.primaryContact, true)
    if (formState.registrationType === 'group' && formState.additionalVisitors.length === 0) {
      errors.additionalVisitors = 'Add at least one visitor to continue.'
    }
    return errors
  }

  if (stepKey === 'visit_details') {
    const errors: Record<string, string> = {}
    const { visitInfo } = formState
    if (!visitInfo.purpose) errors.purpose = 'Purpose of visit is required.'
    if (!visitInfo.preferredDate) errors.preferredDate = 'Preferred visit date is required.'
    else if (visitInfo.preferredDate < todayAsDateInputValue()) errors.preferredDate = 'Preferred visit date cannot be in the past.'
    if (!visitInfo.preferredTime) errors.preferredTime = 'Preferred visit time is required.'
    if (!visitInfo.expectedDuration) errors.expectedDuration = 'Expected duration is required.'
    if (!visitInfo.location) errors.location = 'Location is required.'
    if (!visitInfo.building) errors.building = 'Building is required.'
    return errors
  }

  if (stepKey === 'consent_agreement') {
    // Branch-configured (form-builder): whichever keys the resolved
    // branch's Consent Agreement step currently marks required. `goNext`
    // doesn't call this while the config is still loading, so there's no
    // "not resolved yet" case to default here.
    const missing = requiredConsentKeys.filter((key) => !formState.consent[key])
    if (missing.length > 0) {
      return { consent: 'You must agree to all the required items to continue.' }
    }
    return {}
  }

  return {}
}

export function useVisitorRequestWizard(initial?: VisitorRequestWizardInitialData, branches?: Branch[]) {
  const { submitVisitRequestUseCase } = useAppDependencies()

  const [currentStep, setCurrentStep] = useState(0)
  const [formState, setFormState] = useState<VisitRequestFormState>(() => buildInitialFormState(initial))
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submissionStatus, setSubmissionStatus] = useState<SubmissionStatus>('idle')
  const [trackingId, setTrackingId] = useState<string | undefined>(undefined)
  const [submissionError, setSubmissionError] = useState<string | undefined>(undefined)

  // Resolved the same way `submit` below resolves it for the real
  // request — matching branch name against the publicly listed branches —
  // so the Carried Items/Consent steps render (and validate against) the
  // same branch's Form Builder configuration the backend will actually
  // enforce, once that branch is known (step 1, Visit Info).
  const branchId = useMemo(
    () => branches?.find((branch) => branch.name === formState.visitInfo.location)?.id,
    [branches, formState.visitInfo.location],
  )
  const {
    steps: effectiveFormSteps,
    isLoading: isFormConfigLoading,
    error: formConfigError,
  } = useEffectiveForm(branchId)
  const activeSteps = useMemo(() => getActiveSteps(effectiveFormSteps), [effectiveFormSteps])
  const carriedItemsFields = useMemo(() => findStepFields(effectiveFormSteps, 'carried_items'), [effectiveFormSteps])
  const consentFields = useMemo(() => findStepFields(effectiveFormSteps, 'consent_agreement'), [effectiveFormSteps])
  const requiredConsentKeys = useMemo(
    () => consentFields.filter((field) => field.isRequired).map((field) => field.key),
    [consentFields],
  )
  const lastStepIndex = activeSteps.length > 0 ? activeSteps.length - 1 : 0

  // The active step set can change mid-session once `branchId` resolves
  // from the tenant default to a branch-specific override (design.md's
  // branch-resolution-timing risk) — keep `currentStep` in range rather
  // than pointing past the end of a shorter list.
  useEffect(() => {
    setCurrentStep((step) => Math.min(step, lastStepIndex))
  }, [lastStepIndex])

  // POST /registrations/walk-in wants ID-proof files travelling inline in the
  // final multipart submission, not pre-uploaded. `uploadFile` here just hands
  // the file a local ref so FileUploadField can track/display it; the real
  // File objects are recovered by that ref at submit time below.
  const fileRegistry = useRef(new Map<string, File>())
  // Object URLs are cached per fileRef so repeated renders (e.g. the Review
  // step re-rendering) reuse one URL instead of leaking a new one each time.
  const previewUrlCache = useRef(new Map<string, string>())

  const uploadFile = async (file: File): Promise<string> => {
    const fileRef = crypto.randomUUID()
    fileRegistry.current.set(fileRef, file)
    return fileRef
  }

  const getFilePreviewUrl = (fileRef?: string): string | undefined => {
    if (!fileRef) return undefined
    const cached = previewUrlCache.current.get(fileRef)
    if (cached) return cached
    const file = fileRegistry.current.get(fileRef)
    if (!file) return undefined
    const url = URL.createObjectURL(file)
    previewUrlCache.current.set(fileRef, url)
    return url
  }

  const updateFormState = (next: VisitRequestFormState) => {
    setFormState(next)
    // Clear stale step errors optimistically; goNext re-validates before advancing.
    setErrors({})
  }

  const goNext = () => {
    // While the effective config is still loading, `activeSteps` may not yet
    // reflect the branch's real step list — hold the visitor on the first
    // step rather than advance against a stale/incomplete list.
    if (isFormConfigLoading) return
    const stepErrors = validateStep(activeSteps[currentStep]?.key, formState, requiredConsentKeys)
    if (Object.keys(stepErrors).length > 0) {
      setErrors(stepErrors)
      return
    }
    setErrors({})
    setCurrentStep((step) => Math.min(step + 1, lastStepIndex))
  }

  const goBack = () => {
    setErrors({})
    setCurrentStep((step) => Math.max(step - 1, 0))
  }

  // Jumping to an already-completed step (e.g. via the sidebar) never needs
  // re-validation — only forward movement via goNext does.
  const goToStep = (step: number) => {
    if (step >= currentStep) return
    setErrors({})
    setCurrentStep(step)
  }

  const submit = async () => {
    const primaryContactIdProofFile = formState.primaryContact.idProofFileRef
      ? fileRegistry.current.get(formState.primaryContact.idProofFileRef)
      : undefined
    const primaryContactPhotoFile = formState.primaryContact.profileImageFileRef
      ? fileRegistry.current.get(formState.primaryContact.profileImageFileRef)
      : undefined
    if (!primaryContactIdProofFile || !primaryContactPhotoFile) {
      setSubmissionError('Something went wrong submitting your request. Please try again.')
      setSubmissionStatus('error')
      return
    }

    const visitorIdProofFiles = formState.additionalVisitors
      .map((visitor) => (visitor.idProofFileRef ? fileRegistry.current.get(visitor.idProofFileRef) : undefined))
      .filter((file): file is File => file !== undefined)

    setSubmissionStatus('submitting')
    setSubmissionError(undefined)
    try {
      const response = await submitVisitRequestUseCase.execute(toVisitRequest(formState), {
        primaryContactIdProofFile,
        primaryContactPhotoFile,
        visitorIdProofFiles,
      })
      setTrackingId(response.trackingId)
      setSubmissionStatus('success')
    } catch (error) {
      setSubmissionError(error instanceof Error ? error.message : 'Something went wrong submitting your request. Please try again.')
      setSubmissionStatus('error')
    }
  }

  return {
    currentStep,
    formState,
    setFormState: updateFormState,
    errors,
    goNext,
    goBack,
    goToStep,
    uploadFile,
    getFilePreviewUrl,
    submissionStatus,
    trackingId,
    submissionError,
    submit,
    activeSteps,
    isFormConfigLoading,
    formConfigError,
    carriedItemsFields,
    consentFields,
  }
}
