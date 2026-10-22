import { useEffect, useMemo, useRef, useState } from 'react'
import { validateGroupMinimums } from '../../../components/dynamic-fields/field-group-visibility'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { extractGroupFieldFiles } from '../../../components/dynamic-fields/field-group-visibility'
import type { DynamicFieldValue } from '../../../components/dynamic-fields/DynamicField'
import {
  extractListCustomFieldFiles,
  extractSingleCustomFieldFiles,
  fileUploadFieldsOf,
  findInvitationFields,
  findInvitationFileUploadFields,
  hasMissingRequiredCustomFieldFile,
  requiredFileUploadFieldsOf,
} from '../../../components/dynamic-fields/custom-field-files'
import { findField, findStepFields, findStepGroups, useEffectiveForm } from '../../../hooks/use-effective-form'
import type { VisitorInfoFieldState } from '../../visitor-request/hooks/use-visitor-request-wizard'
import { isValidPhoneNumber } from '../../../utils/is-valid-phone-number'
import { isValidIndianMobileNumber } from '../../../utils/is-valid-indian-mobile-number'
import { todayAsDateInputValue } from '../../../utils/local-date-input-value'
import type { Branch } from '../../../../domain/entities/branch-schema'
import type { Building } from '../../../../domain/entities/building-schema'
import type { StaffVisitorLookup } from '../../../../domain/entities/staff-visitor-lookup-schema'
import { getActiveSteps, type StepKey } from '../../visitor-request/registration-wizard-steps'
import type { SubmissionStatus } from '../../visitor-request/Components/steps/ReviewConfirmStep'
import {
  createInitialStaffFormState,
  toStaffVisitRequest,
  type StaffVisitorFormEntry,
  type StaffVisitRequestFormState,
} from '../types'
import { toUserMessage } from '../../../utils/to-user-message'
import { isValidEmail } from '../../../utils/is-valid-email'

// The backend rejects phone lookups with fewer than 7 digits (422) or more
// than 50 characters, so those are gated client-side instead of sent.
const MIN_PHONE_LOOKUP_DIGITS = 7
const MAX_PHONE_LOOKUP_LENGTH = 50
const digitsOf = (value: string) => value.replace(/\D/g, '')

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
  if (!contact.fullName.trim()) errors.fullName = 'Full name is required.'
  // Only the contact field matching the chosen preferred contact method is
  // mandatory (mirrors the API's `_require_contact_for_method`) — the other
  // field is optional, not both unconditionally.
  if (!contact.preferredContactMethod) {
    errors.preferredContactMethod = 'Preferred contact method is required.'
  } else if (contact.preferredContactMethod === 'email' && !contact.email) {
    errors.email = 'Email is required.'
  } else if ((contact.preferredContactMethod === 'sms' || contact.preferredContactMethod === 'whatsapp') && !contact.phone) {
    errors.phone = 'Phone number is required.'
  }
  if (!errors.email && contact.email.trim() && !isValidEmail(contact.email)) {
    errors.email = 'Enter a valid email address.'
  }
  if (contact.phone && !isValidPhoneNumber(contact.phone)) {
    errors.phone = 'Enter a valid phone number.'
  } else if (
    contact.phone &&
    (contact.preferredContactMethod === 'sms' || contact.preferredContactMethod === 'whatsapp') &&
    !isValidIndianMobileNumber(contact.phone)
  ) {
    errors.phone = 'Enter a valid Indian mobile number for SMS or WhatsApp.'
  }
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

export function useStaffVisitorRegistrationWizard(branches?: Branch[], buildings?: Building[]) {
  const { submitStaffVisitRequestUseCase, trackVisitRequestUseCase, lookupStaffVisitorByEmailUseCase, lookupStaffVisitorByPhoneUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentStep, setCurrentStep] = useState(0)
  const [formState, setFormState] = useState<StaffVisitRequestFormState>(createInitialStaffFormState)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submissionStatus, setSubmissionStatus] = useState<SubmissionStatus>('idle')
  const [trackingId, setTrackingId] = useState<string | undefined>(undefined)
  const [confirmedFullName, setConfirmedFullName] = useState<string | undefined>(undefined)
  const [submissionError, setSubmissionError] = useState<string | undefined>(undefined)

  // Debounced "email/phone → prefill" lookups for the primary contact only
  // (an additional group visitor isn't looked up). Each tracks the last value
  // a lookup was actually issued for so re-renders that don't change it
  // (e.g. typing into another field) don't re-trigger it.
  const lastLookedUpEmailRef = useRef<string | null>(null)
  const lastLookedUpPhoneRef = useRef<string | null>(null)
  const formStateRef = useRef(formState)
  formStateRef.current = formState

  // Applies a lookup match to the primary contact, filling only fields that
  // are still empty so nothing the staff member typed is overwritten.
  // `isCurrent` guards against a response arriving after the triggering
  // field was edited again.
  const applyLookupMatch = (match: StaffVisitorLookup, isCurrent: (entry: StaffVisitorFormEntry) => boolean) => {
    const before = formStateRef.current.primaryContact
    if (!isCurrent(before)) return

    // Mark the other trigger field as already looked up so a prefilled email
    // (or phone) doesn't fire a redundant second lookup.
    if (!before.email.trim() && match.email) lastLookedUpEmailRef.current = match.email.trim().toLowerCase()
    if (!before.phone.trim() && match.phone) lastLookedUpPhoneRef.current = digitsOf(match.phone)

    // The contact-method toggle starts on 'email', so that default counts as unset.
    const methodIsDefault = before.preferredContactMethod === undefined || before.preferredContactMethod === 'email'
    const patch: Partial<StaffVisitorFormEntry> = {}
    if (!before.fullName.trim()) patch.fullName = match.fullName
    if (!before.email.trim() && match.email) patch.email = match.email
    if (!before.phone.trim() && match.phone) patch.phone = match.phone
    if (methodIsDefault && match.preferredContactMethod) patch.preferredContactMethod = match.preferredContactMethod
    if (!before.visitorCategory && match.visitorCategoryId) patch.visitorCategory = match.visitorCategoryId
    if (!before.idProofType && match.idProofType) patch.idProofType = match.idProofType

    const wantsPhoto = !!match.photoUrl && !before.profileImageFileRef
    const wantsIdProof = !!match.idProofUrl && !before.idProofFileRef

    if (Object.keys(patch).length > 0) {
      setFormState((current) =>
        isCurrent(current.primaryContact)
          ? { ...current, primaryContact: { ...current.primaryContact, ...patch } }
          : current,
      )
    }
    if (Object.keys(patch).length > 0 || wantsPhoto || wantsIdProof) {
      toast.success('Existing visitor found — details prefilled.')
    }

    // Best-effort, same pattern as use-visitor-request-wizard.ts's
    // existing-file reuse: fetch the signed URL into a real File and
    // register it, so the upload control shows it prefilled instead
    // of demanding a fresh upload. A fetch failure (expired
    // signature, network) just leaves that field as a normal empty
    // upload control — each file is independent of the other. A null
    // `idProofUrl` (caller lacks documents:view) simply skips that file.
    if (wantsIdProof && match.idProofUrl) {
      fetchExistingStaffFile(match.idProofUrl, 'id-proof')
        .then(async (file) => {
          const fileRef = await uploadFile(file)
          setFormState((current) => {
            if (!isCurrent(current.primaryContact) || current.primaryContact.idProofFileRef) return current
            return { ...current, primaryContact: { ...current.primaryContact, idProofFileRef: fileRef, idProofFileName: file.name } }
          })
        })
        .catch(() => {
          // Leave idProofFileRef unset — field renders as a normal, empty upload control.
        })
    }
    if (wantsPhoto && match.photoUrl) {
      fetchExistingStaffFile(match.photoUrl, 'profile-photo')
        .then(async (file) => {
          const fileRef = await uploadFile(file)
          setFormState((current) => {
            if (!isCurrent(current.primaryContact) || current.primaryContact.profileImageFileRef) return current
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
  }
  const applyLookupMatchRef = useRef(applyLookupMatch)
  applyLookupMatchRef.current = applyLookupMatch

  useEffect(() => {
    const email = formState.primaryContact.email.trim().toLowerCase()
    if (!isValidEmail(email) || lastLookedUpEmailRef.current === email) return

    const timeoutId = setTimeout(() => {
      lastLookedUpEmailRef.current = email
      lookupStaffVisitorByEmailUseCase
        .execute(email)
        .then((match) => {
          if (!match) return
          applyLookupMatchRef.current(match, (entry) => entry.email.trim().toLowerCase() === email)
        })
        .catch(() => {
          // No match, or the lookup failed — leave the form exactly as the
          // staff member typed it.
        })
    }, 400)

    return () => clearTimeout(timeoutId)
  }, [formState.primaryContact.email, lookupStaffVisitorByEmailUseCase])

  useEffect(() => {
    const rawPhone = formState.primaryContact.phone.trim()
    const digits = digitsOf(rawPhone)
    if (digits.length < MIN_PHONE_LOOKUP_DIGITS || rawPhone.length > MAX_PHONE_LOOKUP_LENGTH) return
    if (lastLookedUpPhoneRef.current === digits) return

    const timeoutId = setTimeout(() => {
      lastLookedUpPhoneRef.current = digits
      lookupStaffVisitorByPhoneUseCase
        .execute(rawPhone)
        .then((match) => {
          if (!match) return
          applyLookupMatchRef.current(match, (entry) => digitsOf(entry.phone) === digits)
        })
        .catch(() => {
          // No match, 422, or network failure — leave the form as typed.
        })
    }, 400)

    return () => clearTimeout(timeoutId)
  }, [formState.primaryContact.phone, lookupStaffVisitorByPhoneUseCase])

  const branchId = useMemo(
    () => branches?.find((branch) => branch.name === formState.visitInfo.location)?.id,
    [branches, formState.visitInfo.location],
  )
  const buildingId = useMemo(
    () =>
      buildings?.find(
        (building) => building.name === formState.visitInfo.building && (!branchId || building.branchId === branchId),
      )?.id,
    [buildings, branchId, formState.visitInfo.building],
  )
  const {
    steps: effectiveFormSteps,
    isLoading: isFormConfigLoading,
    error: formConfigError,
  } = useEffectiveForm(branchId)
  const activeSteps = useMemo(() => getActiveSteps(effectiveFormSteps), [effectiveFormSteps])
  const carriedItemsFields = useMemo(() => findStepFields(effectiveFormSteps, 'carried_items'), [effectiveFormSteps])
  // See use-visitor-request-wizard.ts's matching comment.
  const carriedItemsGroups = useMemo(
    () => findStepGroups(effectiveFormSteps, 'carried_items').filter((group) => !group.isSystem),
    [effectiveFormSteps],
  )
  const carriedItemsAllFields = useMemo(
    () => findStepFields(effectiveFormSteps, 'carried_items').filter((field) => !field.isSystem),
    [effectiveFormSteps],
  )
  const carriedItemsCustomFields = useMemo(() => {
    const nonSystemGroupIds = new Set(carriedItemsGroups.map((group) => group.id))
    return carriedItemsAllFields.filter((field) => field.groupId === null || !nonSystemGroupIds.has(field.groupId))
  }, [carriedItemsAllFields, carriedItemsGroups])
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
  // See use-visitor-request-wizard.ts's matching comment on the `groupId`
  // (not `key`) based exclusion.
  const visitorInfoCustomFields = useMemo(() => {
    const nonSystemGroupIds = new Set(visitorInfoGroups.map((group) => group.id))
    return visitorInfoAllFields.filter((field) => field.groupId === null || !nonSystemGroupIds.has(field.groupId))
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
  // See use-visitor-request-wizard.ts's matching comment.
  const vehicleInfoCustomFields = useMemo(() => {
    const nonSystemGroupIds = new Set(vehicleInfoGroups.map((group) => group.id))
    return vehicleInfoAllFields.filter((field) => field.groupId === null || !nonSystemGroupIds.has(field.groupId))
  }, [vehicleInfoAllFields, vehicleInfoGroups])
  // See use-visitor-request-wizard.ts's matching comment.
  const invitationCustomFields = useMemo(() => findInvitationFields(effectiveFormSteps), [effectiveFormSteps])
  // See use-visitor-request-wizard.ts's matching comment.
  const visitorInfoFileUploadFields = useMemo(() => fileUploadFieldsOf(visitorInfoCustomFields), [visitorInfoCustomFields])
  const visitorInfoRequiredFileUploadFields = useMemo(
    () => requiredFileUploadFieldsOf(visitorInfoCustomFields),
    [visitorInfoCustomFields],
  )
  const vehicleInfoFileUploadFields = useMemo(() => fileUploadFieldsOf(vehicleInfoCustomFields), [vehicleInfoCustomFields])
  const vehicleInfoRequiredFileUploadFields = useMemo(
    () => requiredFileUploadFieldsOf(vehicleInfoCustomFields),
    [vehicleInfoCustomFields],
  )
  const invitationFileUploadFields = useMemo(() => findInvitationFileUploadFields(effectiveFormSteps), [effectiveFormSteps])
  const invitationRequiredFileUploadFields = useMemo(
    () => invitationFileUploadFields.filter((field) => field.isRequired),
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
    const stepErrors = {
      ...validateStep(activeSteps[currentStep]?.key, formState, requiredConsentKeys, visitorInfoFields),
      ...validateGroupMinimums(activeSteps[currentStep]?.groups ?? [], formState.groupValues, {
        registration_type: formState.registrationType,
        ...formState.primaryContact.customFieldValues,
        ...formState.customFieldValues,
      }),
    }
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
    // See use-visitor-request-wizard.ts's matching comment.
    const missingRequiredCustomFieldFile =
      hasMissingRequiredCustomFieldFile(visitorInfoRequiredFileUploadFields, [formState.primaryContact.customFieldValues]) ||
      hasMissingRequiredCustomFieldFile(
        visitorInfoRequiredFileUploadFields,
        formState.additionalVisitors.map((visitor) => visitor.customFieldValues),
      ) ||
      hasMissingRequiredCustomFieldFile(
        vehicleInfoRequiredFileUploadFields,
        formState.vehicles.map((vehicle) => vehicle.customFieldValues as Record<string, DynamicFieldValue> | undefined),
      ) ||
      hasMissingRequiredCustomFieldFile(invitationRequiredFileUploadFields, [formState.customFieldValues])
    if (idProofMissing || photoMissing || missingRequiredCustomFieldFile || !branchId) {
      const message = !branchId
        ? 'Location could not be matched to a branch. Reload the page and select the location again.'
        : idProofMissing
          ? 'ID proof is required — please go back and upload it.'
          : photoMissing
            ? 'Profile photo is required — please go back and upload it.'
            : 'A required file upload is missing — please go back and upload it.'
      setSubmissionError(message)
      setSubmissionStatus('error')
      toast.error(message)
      return
    }

    const visitorIdProofFiles = formState.additionalVisitors
      .map((visitor) => (visitor.idProofFileRef ? fileRegistry.current.get(visitor.idProofFileRef) : undefined))
      .filter((file): file is File => file !== undefined)
    // See use-visitor-request-wizard.ts's matching comment.
    const visitorPhotoFiles = formState.additionalVisitors
      .map((visitor) => (visitor.profileImageFileRef ? fileRegistry.current.get(visitor.profileImageFileRef) : undefined))
      .filter((file): file is File => file !== undefined)

    // See use-visitor-request-wizard.ts's matching comment.
    const { sanitizedGroupValues, groupFieldFiles } = extractGroupFieldFiles(
      effectiveFormSteps,
      formState.groupValues,
      fileRegistry.current,
    )

    // See use-visitor-request-wizard.ts's matching comment.
    const { sanitizedValues: sanitizedPrimaryContactCustomFieldValues, files: primaryContactCustomFieldFiles } =
      extractSingleCustomFieldFiles(visitorInfoFileUploadFields, formState.primaryContact.customFieldValues, fileRegistry.current)
    const { sanitizedValuesList: sanitizedVisitorCustomFieldValuesList, filesByKey: visitorCustomFieldFiles } =
      extractListCustomFieldFiles(
        visitorInfoFileUploadFields,
        formState.additionalVisitors.map((visitor) => visitor.customFieldValues),
        fileRegistry.current,
      )
    const { sanitizedValuesList: sanitizedVehicleCustomFieldValuesList, filesByKey: vehicleCustomFieldFiles } =
      extractListCustomFieldFiles(
        vehicleInfoFileUploadFields,
        formState.vehicles.map((vehicle) => vehicle.customFieldValues as Record<string, DynamicFieldValue> | undefined),
        fileRegistry.current,
      )
    const { sanitizedValues: sanitizedCustomFieldValues, files: customFieldFiles } = extractSingleCustomFieldFiles(
      invitationFileUploadFields,
      formState.customFieldValues,
      fileRegistry.current,
    )

    setSubmissionStatus('submitting')
    setSubmissionError(undefined)
    try {
      const response = await submitStaffVisitRequestUseCase.execute(
        toStaffVisitRequest(
          {
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
          },
          {
            visitorInfoFields: visitorInfoCustomFields,
            vehicleInfoFields: vehicleInfoCustomFields,
            invitationFields: invitationCustomFields,
            consentFields,
            steps: effectiveFormSteps,
            branchId,
            buildingId,
          },
        ),
        {
          primaryContactIdProofFile,
          primaryContactPhotoFile,
          visitorIdProofFiles,
          visitorPhotoFiles,
          groupFieldFiles,
          primaryContactCustomFieldFiles,
          visitorCustomFieldFiles,
          vehicleCustomFieldFiles,
          customFieldFiles,
        },
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
      const message = toUserMessage(error, 'Something went wrong submitting your request. Please try again.')
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
    carriedItemsCustomFields,
    carriedItemsGroups,
    carriedItemsAllFields,
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
