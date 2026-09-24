import { useEffect, useMemo, useRef, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { extractGroupFieldFiles } from '../../../components/dynamic-fields/field-group-visibility'
import type { DynamicFieldValue } from '../../../components/dynamic-fields/DynamicField'
import {
  extractListCustomFieldFiles,
  extractSingleCustomFieldFiles,
  fileUploadFieldKeysOf,
  findInvitationFileUploadFields,
  hasMissingRequiredCustomFieldFile,
  requiredFileUploadFieldKeysOf,
} from '../../../components/dynamic-fields/custom-field-files'
import { findField, findStepFields, findStepGroups, useEffectiveForm } from '../../../hooks/use-effective-form'
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
    return errors
  }

  if (stepKey === 'visit_details') {
    const errors: Record<string, string> = {}
    const { visitInfo } = formState
    if (!visitInfo.purpose) errors.purpose = 'Purpose of visit is required.'
    if (!visitInfo.preferredDate) errors.preferredDate = 'Preferred visit date is required.'
    else if (visitInfo.preferredDate < todayAsDateInputValue()) errors.preferredDate = 'Preferred visit date cannot be in the past.'
    if (!visitInfo.preferredTime) errors.preferredTime = 'Preferred visit time is required.'
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
  const { submitStaffVisitRequestUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentStep, setCurrentStep] = useState(0)
  const [formState, setFormState] = useState<StaffVisitRequestFormState>(createInitialStaffFormState)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submissionStatus, setSubmissionStatus] = useState<SubmissionStatus>('idle')
  const [trackingId, setTrackingId] = useState<string | undefined>(undefined)
  const [submissionError, setSubmissionError] = useState<string | undefined>(undefined)

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
    const idProofType = findField(effectiveFormSteps, 'visitor_info', 'id_proof_type')
    const profilePhoto = findField(effectiveFormSteps, 'visitor_info', 'profile_photo')
    return {
      idProofActive: idProofUpload !== undefined,
      idProofRequired: idProofUpload?.isRequired ?? false,
      idProofOptions: idProofType?.options ?? [],
      profilePhotoActive: profilePhoto !== undefined,
      profilePhotoRequired: profilePhoto?.isRequired ?? false,
    }
  }, [effectiveFormSteps])
  // See use-visitor-request-wizard.ts's matching comment.
  const purposeOfVisitOptions = useMemo(
    () => findField(effectiveFormSteps, 'visit_details', 'purpose_of_visit')?.options ?? [],
    [effectiveFormSteps],
  )
  const vehicleInfoFields = useMemo(() => {
    const makeModel = findField(effectiveFormSteps, 'vehicle_info', 'make_model')
    const color = findField(effectiveFormSteps, 'vehicle_info', 'color')
    const vehicleType = findField(effectiveFormSteps, 'vehicle_info', 'vehicle_type')
    return {
      makeModelActive: makeModel !== undefined,
      makeModelRequired: makeModel?.isRequired ?? false,
      colorActive: color !== undefined,
      colorRequired: color?.isRequired ?? false,
      vehicleTypeOptions: vehicleType?.options ?? [],
    }
  }, [effectiveFormSteps])
  // Admin-authored (non-system) fields per step, and Visitor Info's own
  // field groups — see use-visitor-request-wizard.ts's matching comment.
  const visitorInfoGroups = useMemo(
    () => findStepGroups(effectiveFormSteps, 'visitor_info').filter((group) => !group.isSystem),
    [effectiveFormSteps],
  )
  const visitorInfoAllFields = useMemo(
    () => findStepFields(effectiveFormSteps, 'visitor_info').filter((field) => !field.isSystem),
    [effectiveFormSteps],
  )
  const visitorInfoCustomFields = useMemo(() => {
    const groupedFieldKeys = new Set(visitorInfoGroups.flatMap((group) => group.fieldKeys))
    return visitorInfoAllFields.filter((field) => !groupedFieldKeys.has(field.key))
  }, [visitorInfoAllFields, visitorInfoGroups])
  const visitDetailsCustomFields = useMemo(
    () => findStepFields(effectiveFormSteps, 'visit_details').filter((field) => !field.isSystem),
    [effectiveFormSteps],
  )
  // See use-visitor-request-wizard.ts's matching comment.
  const vehicleInfoGroups = useMemo(
    () => findStepGroups(effectiveFormSteps, 'vehicle_info').filter((group) => !group.isSystem),
    [effectiveFormSteps],
  )
  const vehicleInfoAllFields = useMemo(
    () => findStepFields(effectiveFormSteps, 'vehicle_info').filter((field) => !field.isSystem),
    [effectiveFormSteps],
  )
  const vehicleInfoCustomFields = useMemo(() => {
    const groupedFieldKeys = new Set(vehicleInfoGroups.flatMap((group) => group.fieldKeys))
    return vehicleInfoAllFields.filter((field) => !groupedFieldKeys.has(field.key))
  }, [vehicleInfoAllFields, vehicleInfoGroups])
  // See use-visitor-request-wizard.ts's matching comment.
  const visitorInfoFileUploadKeys = useMemo(() => fileUploadFieldKeysOf(visitorInfoCustomFields), [visitorInfoCustomFields])
  const visitorInfoRequiredFileUploadKeys = useMemo(
    () => requiredFileUploadFieldKeysOf(visitorInfoCustomFields),
    [visitorInfoCustomFields],
  )
  const vehicleInfoFileUploadKeys = useMemo(() => fileUploadFieldKeysOf(vehicleInfoCustomFields), [vehicleInfoCustomFields])
  const vehicleInfoRequiredFileUploadKeys = useMemo(
    () => requiredFileUploadFieldKeysOf(vehicleInfoCustomFields),
    [vehicleInfoCustomFields],
  )
  const invitationFileUploadFields = useMemo(() => findInvitationFileUploadFields(effectiveFormSteps), [effectiveFormSteps])
  const invitationFileUploadKeys = useMemo(() => invitationFileUploadFields.map((field) => field.key), [invitationFileUploadFields])
  const invitationRequiredFileUploadKeys = useMemo(
    () => invitationFileUploadFields.filter((field) => field.isRequired).map((field) => field.key),
    [invitationFileUploadFields],
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
    // See use-visitor-request-wizard.ts's matching comment.
    const missingRequiredCustomFieldFile =
      hasMissingRequiredCustomFieldFile(visitorInfoRequiredFileUploadKeys, [formState.primaryContact.customFieldValues]) ||
      hasMissingRequiredCustomFieldFile(
        visitorInfoRequiredFileUploadKeys,
        formState.additionalVisitors.map((visitor) => visitor.customFieldValues),
      ) ||
      hasMissingRequiredCustomFieldFile(
        vehicleInfoRequiredFileUploadKeys,
        formState.vehicles.map((vehicle) => vehicle.customFieldValues as Record<string, DynamicFieldValue> | undefined),
      ) ||
      hasMissingRequiredCustomFieldFile(invitationRequiredFileUploadKeys, [formState.customFieldValues])
    if (idProofMissing || photoMissing || missingRequiredCustomFieldFile || !branchId) {
      setSubmissionError('Something went wrong submitting your request. Please try again.')
      setSubmissionStatus('error')
      toast.error('Something went wrong submitting your request. Please try again.')
      return
    }

    const visitorIdProofFiles = formState.additionalVisitors
      .map((visitor) => (visitor.idProofFileRef ? fileRegistry.current.get(visitor.idProofFileRef) : undefined))
      .filter((file): file is File => file !== undefined)

    // See use-visitor-request-wizard.ts's matching comment.
    const { sanitizedGroupValues, groupFieldFiles } = extractGroupFieldFiles(
      effectiveFormSteps,
      formState.groupValues,
      fileRegistry.current,
    )

    // See use-visitor-request-wizard.ts's matching comment.
    const { sanitizedValues: sanitizedPrimaryContactCustomFieldValues, files: primaryContactCustomFieldFiles } =
      extractSingleCustomFieldFiles(visitorInfoFileUploadKeys, formState.primaryContact.customFieldValues, fileRegistry.current)
    const { sanitizedValuesList: sanitizedVisitorCustomFieldValuesList, filesByKey: visitorCustomFieldFiles } =
      extractListCustomFieldFiles(
        visitorInfoFileUploadKeys,
        formState.additionalVisitors.map((visitor) => visitor.customFieldValues),
        fileRegistry.current,
      )
    const { sanitizedValuesList: sanitizedVehicleCustomFieldValuesList, filesByKey: vehicleCustomFieldFiles } =
      extractListCustomFieldFiles(
        vehicleInfoFileUploadKeys,
        formState.vehicles.map((vehicle) => vehicle.customFieldValues as Record<string, DynamicFieldValue> | undefined),
        fileRegistry.current,
      )
    const { sanitizedValues: sanitizedCustomFieldValues, files: customFieldFiles } = extractSingleCustomFieldFiles(
      invitationFileUploadKeys,
      formState.customFieldValues,
      fileRegistry.current,
    )

    setSubmissionStatus('submitting')
    setSubmissionError(undefined)
    try {
      const response = await submitStaffVisitRequestUseCase.execute(
        toStaffVisitRequest({
          ...formState,
          groupValues: sanitizedGroupValues,
          customFieldValues: sanitizedCustomFieldValues,
          primaryContact: { ...formState.primaryContact, customFieldValues: sanitizedPrimaryContactCustomFieldValues },
          additionalVisitors: formState.additionalVisitors.map((visitor, index) => ({
            ...visitor,
            customFieldValues: sanitizedVisitorCustomFieldValuesList[index],
          })),
          vehicles: formState.vehicles.map((vehicle, index) => ({
            ...vehicle,
            customFieldValues: sanitizedVehicleCustomFieldValuesList[index],
          })),
        }),
        {
          primaryContactIdProofFile,
          primaryContactPhotoFile,
          visitorIdProofFiles,
          groupFieldFiles,
          primaryContactCustomFieldFiles,
          visitorCustomFieldFiles,
          vehicleCustomFieldFiles,
          customFieldFiles,
        },
        branchId,
      )
      setTrackingId(response.trackingId)
      setSubmissionStatus('success')
      toast.success('Visitor registered successfully.')
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
    submissionError,
    submit,
    reset,
    activeSteps,
    isFormConfigLoading,
    formConfigError,
    carriedItemsFields,
    consentFields,
    visitorInfoFields,
    purposeOfVisitOptions,
    vehicleInfoFields,
    visitorInfoCustomFields,
    visitorInfoGroups,
    visitorInfoAllFields,
    visitDetailsCustomFields,
    vehicleInfoCustomFields,
    vehicleInfoGroups,
    vehicleInfoAllFields,
  }
}
