import { useEffect, useMemo, useRef, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { findField, findStepFields, useEffectiveForm } from '../../../hooks/use-effective-form'
import type { VisitorInfoFieldState } from '../../visitor-request/hooks/use-visitor-request-wizard'
import { isValidPhoneNumber } from '../../../utils/is-valid-phone-number'
import { todayAsDateInputValue } from '../../../utils/local-date-input-value'
import type { Branch } from '../../../../domain/entities/branch-schema'
import { getActiveSteps, type StepKey } from '../../visitor-request/registration-wizard-steps'
import type { SubmissionStatus } from '../../visitor-request/Components/steps/ReviewConfirmStep'
import {
  createInitialStaffFormState,
  toStaffVisitRequest,
  type StaffVisitorFormEntry,
  type StaffVisitRequestFormState,
} from '../types'

// Matches the input's own `type="email"` validation closely enough to gate
// a lookup request without firing on every keystroke of a half-typed address.
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

// Mirrors use-visitor-request-wizard.ts's matching helper — kept local
// rather than shared across features for one small helper.
const EXTENSION_BY_CONTENT_TYPE: Record<string, string> = {
  'image/png': 'png',
  'image/jpeg': 'jpg',
  'application/pdf': 'pdf',
}

async function fetchExistingStaffFile(url: string, baseName: string): Promise<File> {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`Failed to fetch existing file (${response.status})`)
  const blob = await response.blob()
  const contentType = blob.type || 'application/octet-stream'
  const extension = EXTENSION_BY_CONTENT_TYPE[contentType] ?? 'bin'
  return new File([blob], `${baseName}.${extension}`, { type: contentType })
}

function validateStaffVisitorContact(contact: StaffVisitorFormEntry, visitorInfoFields: VisitorInfoFieldState): Record<string, string> {
  const errors: Record<string, string> = {}
  if (!contact.fullName) errors.fullName = 'Full name is required.'
  // Only the contact field matching the chosen preferred contact method is
  // mandatory (mirrors the API's `_require_contact_for_method`) — the other
  // field is optional, not both unconditionally.
  if (!contact.preferredContactMethod) {
    errors.preferredContactMethod = 'Preferred contact method is required.'
  } else if (contact.preferredContactMethod === 'email' && !contact.email) {
    errors.email = 'Email is required.'
  } else if (contact.preferredContactMethod === 'sms' && !contact.phone) {
    errors.phone = 'Phone number is required.'
  }
  if (contact.phone && !isValidPhoneNumber(contact.phone)) errors.phone = 'Enter a valid phone number.'
  if (!contact.visitorCategory) errors.visitorCategory = 'Visitor category is required.'
  if (visitorInfoFields.idProofActive && visitorInfoFields.idProofRequired) {
    if (!contact.idProofType) errors.idProofType = 'ID proof type is required.'
    if (!contact.idProofFileRef) errors.idProofFileRef = 'ID proof file is required.'
  }
  // Profile image is only collected for the primary contact (PrimaryContactCard),
  // not the additional-visitor draft form, so it's only enforced here.
  if (visitorInfoFields.profilePhotoActive && visitorInfoFields.profilePhotoRequired && !contact.profileImageFileRef) {
    errors.profileImageFileRef = 'Profile image is required.'
  }
  return errors
}

// Keyed by the step's form-builder `key`, not its numeric position — see
// use-visitor-request-wizard.ts's matching comment.
function validateStep(
  stepKey: StepKey | string | undefined,
  formState: StaffVisitRequestFormState,
  requiredConsentKeys: string[],
  visitorInfoFields: VisitorInfoFieldState,
): Record<string, string> {
  if (stepKey === 'visitor_info') {
    const errors = validateStaffVisitorContact(formState.primaryContact, visitorInfoFields)
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
    // `expected_duration` is structurally required by the backend
    // regardless of form-builder configuration — see
    // use-visitor-request-wizard.ts's matching comment.
    if (!visitInfo.expectedDuration) errors.expectedDuration = 'Expected duration is required.'
    if (!visitInfo.location) errors.location = 'Location is required.'
    if (!visitInfo.building) errors.building = 'Building is required.'
    return errors
  }

  if (stepKey === 'consent_agreement') {
    // Branch-configured (form-builder) — see
    // use-visitor-request-wizard.ts's matching comment.
    const missing = requiredConsentKeys.filter((key) => !formState.consent[key])
    if (missing.length > 0) {
      return { consent: 'You must agree to all the required items to continue.' }
    }
    return {}
  }

  return {}
}

export function useStaffVisitorRegistrationWizard(branches?: Branch[]) {
  const { submitStaffVisitRequestUseCase, trackVisitRequestUseCase, lookupStaffVisitorByEmailUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentStep, setCurrentStep] = useState(0)
  const [formState, setFormState] = useState<StaffVisitRequestFormState>(createInitialStaffFormState)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submissionStatus, setSubmissionStatus] = useState<SubmissionStatus>('idle')
  const [trackingId, setTrackingId] = useState<string | undefined>(undefined)
  const [confirmedFullName, setConfirmedFullName] = useState<string | undefined>(undefined)
  const [submissionError, setSubmissionError] = useState<string | undefined>(undefined)

  // Debounced "email → prefill" lookup for the primary contact only (an
  // additional group visitor's email isn't looked up). Tracks the last email
  // a lookup was actually issued for so re-renders that don't change the
  // email (e.g. typing into another field) don't re-trigger it.
  const lastLookedUpEmailRef = useRef<string | null>(null)
  useEffect(() => {
    const email = formState.primaryContact.email.trim().toLowerCase()
    if (!EMAIL_PATTERN.test(email) || lastLookedUpEmailRef.current === email) return

    const timeoutId = setTimeout(() => {
      lastLookedUpEmailRef.current = email
      lookupStaffVisitorByEmailUseCase
        .execute(email)
        .then((match) => {
          if (!match) return
          setFormState((current) => {
            // The staff member may have edited the email again while the
            // request was in flight — only apply a match for the email it
            // was actually issued for.
            if (current.primaryContact.email.trim().toLowerCase() !== email) return current
            return {
              ...current,
              primaryContact: {
                ...current.primaryContact,
                fullName: match.fullName,
                phone: match.phone ?? current.primaryContact.phone,
                preferredContactMethod: match.preferredContactMethod ?? current.primaryContact.preferredContactMethod,
                visitorCategory: match.visitorCategoryId ?? current.primaryContact.visitorCategory,
                idProofType: match.idProofType ?? current.primaryContact.idProofType,
              },
            }
          })
          toast.success('Existing visitor found — details prefilled.')

          // Best-effort, same pattern as use-visitor-request-wizard.ts's
          // existing-file reuse: fetch the signed URL into a real File and
          // register it, so the upload control shows it prefilled instead
          // of demanding a fresh upload. A fetch failure (expired
          // signature, network) just leaves that field as a normal empty
          // upload control — each file is independent of the other.
          if (match.idProofUrl) {
            fetchExistingStaffFile(match.idProofUrl, 'id-proof')
              .then(async (file) => {
                const fileRef = await uploadFile(file)
                setFormState((current) => {
                  if (current.primaryContact.email.trim().toLowerCase() !== email) return current
                  return { ...current, primaryContact: { ...current.primaryContact, idProofFileRef: fileRef, idProofFileName: file.name } }
                })
              })
              .catch(() => {
                // Leave idProofFileRef unset — field renders as a normal, empty upload control.
              })
          }
          if (match.photoUrl) {
            fetchExistingStaffFile(match.photoUrl, 'profile-photo')
              .then(async (file) => {
                const fileRef = await uploadFile(file)
                setFormState((current) => {
                  if (current.primaryContact.email.trim().toLowerCase() !== email) return current
                  return {
                    ...current,
                    primaryContact: { ...current.primaryContact, profileImageFileRef: fileRef, profileImageFileName: file.name },
                  }
                })
              })
              .catch(() => {
                // Leave profileImageFileRef unset — field renders as a normal, empty upload control.
              })
          }
        })
        .catch(() => {
          // No match, or the lookup failed — leave the form exactly as the
          // staff member typed it.
        })
    }, 400)

    return () => clearTimeout(timeoutId)
  }, [formState.primaryContact.email, lookupStaffVisitorByEmailUseCase, toast])

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
  const visitorInfoFields = useMemo<VisitorInfoFieldState>(() => {
    const idProofUpload = findField(effectiveFormSteps, 'visitor_info', 'id_proof_upload')
    const profilePhoto = findField(effectiveFormSteps, 'visitor_info', 'profile_photo')
    return {
      idProofActive: idProofUpload !== undefined,
      idProofRequired: idProofUpload?.isRequired ?? false,
      profilePhotoActive: profilePhoto !== undefined,
      profilePhotoRequired: profilePhoto?.isRequired ?? false,
    }
  }, [effectiveFormSteps])
  const additionalNotesActive = useMemo(
    () => findField(effectiveFormSteps, 'visit_details', 'additional_notes') !== undefined,
    [effectiveFormSteps],
  )
  const vehicleInfoFields = useMemo(() => {
    const makeModel = findField(effectiveFormSteps, 'vehicle_info', 'make_model')
    const color = findField(effectiveFormSteps, 'vehicle_info', 'color')
    return {
      makeModelActive: makeModel !== undefined,
      makeModelRequired: makeModel?.isRequired ?? false,
      colorActive: color !== undefined,
      colorRequired: color?.isRequired ?? false,
    }
  }, [effectiveFormSteps])
  // Admin-authored (non-system) fields per step — see
  // use-visitor-request-wizard.ts's matching comment.
  const visitorInfoCustomFields = useMemo(
    () => findStepFields(effectiveFormSteps, 'visitor_info').filter((field) => !field.isSystem),
    [effectiveFormSteps],
  )
  const visitDetailsCustomFields = useMemo(
    () => findStepFields(effectiveFormSteps, 'visit_details').filter((field) => !field.isSystem),
    [effectiveFormSteps],
  )
  const vehicleInfoCustomFields = useMemo(
    () => findStepFields(effectiveFormSteps, 'vehicle_info').filter((field) => !field.isSystem),
    [effectiveFormSteps],
  )
  const lastStepIndex = activeSteps.length > 0 ? activeSteps.length - 1 : 0

  // See use-visitor-request-wizard.ts's matching effect for why this is needed.
  useEffect(() => {
    setCurrentStep((step) => Math.min(step, lastStepIndex))
  }, [lastStepIndex])

  // POST /invitations wants ID-proof files travelling inline in the final
  // multipart submission, not pre-uploaded. `uploadFile` here just hands the
  // file a local ref so InlineFileUpload can track/display it; the real File
  // objects are recovered by that ref at submit time below.
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

  const updateFormState = (next: StaffVisitRequestFormState) => {
    setFormState(next)
    // Clear stale step errors optimistically; goNext re-validates before advancing.
    setErrors({})
  }

  const goNext = () => {
    // See use-visitor-request-wizard.ts's matching guard.
    if (isFormConfigLoading) return
    const stepErrors = validateStep(activeSteps[currentStep]?.key, formState, requiredConsentKeys, visitorInfoFields)
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

  // Jumping to an already-completed step (e.g. via the stepper) never needs
  // re-validation — only forward movement via goNext does.
  const goToStep = (step: number) => {
    if (step >= currentStep) return
    setErrors({})
    setCurrentStep(step)
  }

  const reset = () => {
    setFormState(createInitialStaffFormState())
    setCurrentStep(0)
    setErrors({})
    setSubmissionStatus('idle')
    setTrackingId(undefined)
    setConfirmedFullName(undefined)
    setSubmissionError(undefined)
  }

  const submit = async () => {
    const primaryContactIdProofFile = formState.primaryContact.idProofFileRef
      ? fileRegistry.current.get(formState.primaryContact.idProofFileRef)
      : undefined
    const primaryContactPhotoFile = formState.primaryContact.profileImageFileRef
      ? fileRegistry.current.get(formState.primaryContact.profileImageFileRef)
      : undefined
    const branchId = branches?.find((branch) => branch.name === formState.visitInfo.location)?.id
    const idProofMissing = visitorInfoFields.idProofActive && visitorInfoFields.idProofRequired && !primaryContactIdProofFile
    const photoMissing = visitorInfoFields.profilePhotoActive && visitorInfoFields.profilePhotoRequired && !primaryContactPhotoFile
    if (idProofMissing || photoMissing || !branchId) {
      setSubmissionError('Something went wrong submitting your request. Please try again.')
      setSubmissionStatus('error')
      toast.error('Something went wrong submitting your request. Please try again.')
      return
    }

    const visitorIdProofFiles = formState.additionalVisitors
      .map((visitor) => (visitor.idProofFileRef ? fileRegistry.current.get(visitor.idProofFileRef) : undefined))
      .filter((file): file is File => file !== undefined)

    setSubmissionStatus('submitting')
    setSubmissionError(undefined)
    try {
      const response = await submitStaffVisitRequestUseCase.execute(
        toStaffVisitRequest(formState),
        { primaryContactIdProofFile, primaryContactPhotoFile, visitorIdProofFiles },
        branchId,
      )
      setTrackingId(response.trackingId)
      setSubmissionStatus('success')
      toast.success('Visitor registered successfully.')
      // Best-effort: see use-visitor-request-wizard.ts's matching call —
      // the create response never carries the primary contact's name, so
      // look it up via the public tracking lookup instead. A failure here
      // doesn't affect the already-successful submission.
      trackVisitRequestUseCase
        .execute(response.trackingId)
        .then((lookup) => setConfirmedFullName(lookup.primaryContactFullName))
        .catch(() => {
          // Leave confirmedFullName unset — the success screen just omits it.
        })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Something went wrong submitting your request. Please try again.'
      setSubmissionError(message)
      setSubmissionStatus('error')
      toast.error(message)
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
    confirmedFullName,
    submissionError,
    submit,
    reset,
    activeSteps,
    isFormConfigLoading,
    formConfigError,
    carriedItemsFields,
    consentFields,
    visitorInfoFields,
    additionalNotesActive,
    vehicleInfoFields,
    visitorInfoCustomFields,
    visitDetailsCustomFields,
    vehicleInfoCustomFields,
  }
}
