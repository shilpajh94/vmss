import { useEffect, useMemo, useRef, useState } from 'react'
import { validateGroupMinimums } from '../../../components/dynamic-fields/field-group-visibility'
import { useAppDependencies } from '../../../context/app-dependencies-context'
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
import { isValidPhoneNumber } from '../../../utils/is-valid-phone-number'
import { todayAsDateInputValue } from '../../../utils/local-date-input-value'
import type { Branch } from '../../../../domain/entities/branch-schema'
import type { Building } from '../../../../domain/entities/building-schema'
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
  // `fullName`/`preferredContactMethod`/`idProofType` are only populated for a
  // returning visitor (visitor-return-history's prefill) — a fresh OTP
  // verification only ever supplies `email`/`phone`. `idProofUrl`/`photoUrl`,
  // when present, point at the visitor's prior ID-proof document/photo and
  // are fetched and offered as a reusable existing file (see the effect in
  // useVisitorRequestWizard below) rather than always requiring a fresh upload.
  primaryContact?: Partial<
    Pick<VisitorFormEntry, 'fullName' | 'email' | 'phone' | 'preferredContactMethod' | 'idProofType' | 'visitorCategory'>
  > & {
    idProofUrl?: string
    photoUrl?: string
  }
}

const EXTENSION_BY_CONTENT_TYPE: Record<string, string> = {
  'image/png': 'png',
  'image/jpeg': 'jpg',
  'application/pdf': 'pdf',
}

// Resolves a returning visitor's presigned ID-proof/photo URL into a real
// `File`, so it can travel through the same fileRegistry/submit path as a
// freshly picked file (design.md Decision 1). Throws on any fetch failure
// (network, non-2xx, or CORS) — the caller falls back to a fresh-upload
// field rather than surfacing this as a wizard-blocking error.
async function fetchExistingFile(url: string, baseName: string): Promise<File> {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`Failed to fetch existing file (${response.status})`)
  const blob = await response.blob()
  const contentType = blob.type || 'application/octet-stream'
  const extension = EXTENSION_BY_CONTENT_TYPE[contentType] ?? 'bin'
  return new File([blob], `${baseName}.${extension}`, { type: contentType })
}

// `host`/`department_to_visit` are seeded `isSystem` fields the backend
// re-added as active, but the wizard doesn't collect or submit either (see
// `visit-request-schema.ts`'s "intentionally absent" note) — they're
// display-only here, allow-listed past the generic `!isSystem` exclusion so
// they still show up wherever the effective form reports them active.
const DISPLAY_ONLY_SYSTEM_FIELD_KEYS = new Set(['host', 'department_to_visit'])

function buildInitialFormState(initial?: VisitorRequestWizardInitialData): VisitRequestFormState {
  const formState = createInitialFormState()
  if (initial?.registrationType) formState.registrationType = initial.registrationType
  if (initial?.primaryContact) {
    // idProofUrl/photoUrl aren't part of VisitorFormEntry — they're resolved
    // into real fileRefs by the existing-file effect below, not spread here.
    const { idProofUrl, photoUrl, ...primaryContactFields } = initial.primaryContact
    formState.primaryContact = { ...formState.primaryContact, ...primaryContactFields }
  }
  return formState
}

/** Branch-configured (form-builder) requiredness for the Visitor Info
 * step's ID-proof and profile-photo fields — mirrors
 * `form_builder/validation.py::is_field_required`'s own reading exactly:
 * `active` is the field's mere presence in the effective form (`publish()`
 * excludes inactive fields from the snapshot entirely), `required` only
 * matters when active.
 */
export interface VisitorInfoFieldState {
  idProofActive: boolean
  idProofRequired: boolean
  /** Branch-configured (form-builder) ID Proof Type choices — the
   * field's own `options`, not a fixed set
   * (make-id-proof-and-vehicle-type-configurable). */
  idProofOptions: string[]
  profilePhotoActive: boolean
  profilePhotoRequired: boolean
}

// `isPrimary` gates the preferred-contact-method-matching rule: the primary
// contact (or the individual visitor) must supply the field matching their
// chosen preferred contact method, while an additional group visitor — who
// has no preferred contact method of their own — just needs at least one of
// email or phone, mirroring the API's `VisitorSubmit`/`_require_reachable_contact`.
function validateVisitorContact(
  contact: VisitorFormEntry,
  isPrimary: boolean,
  visitorInfoFields: VisitorInfoFieldState,
): Record<string, string> {
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
  if (visitorInfoFields.idProofActive && visitorInfoFields.idProofRequired) {
    if (!contact.idProofType) errors.idProofType = 'ID proof type is required.'
    if (!contact.idProofFileRef) errors.idProofFileRef = 'ID proof file is required.'
  }
  // Profile image is only collected for the primary contact (VisitorFieldsForm
  // only renders it when showExtendedFields is set, which the additional-visitor
  // draft form disables), so only enforce it there.
  if (isPrimary && visitorInfoFields.profilePhotoActive && visitorInfoFields.profilePhotoRequired && !contact.profileImageFileRef) {
    errors.profileImageFileRef = 'Profile image is required.'
  }
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
  visitorInfoFields: VisitorInfoFieldState,
  branchResolved: boolean,
): Record<string, string> {
  if (stepKey === 'visitor_info') {
    const errors = validateVisitorContact(formState.primaryContact, true, visitorInfoFields)
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
    else if (!branchResolved) errors.location = 'Select a valid location from the list (locations may have failed to load — reload and retry).'
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

export function useVisitorRequestWizard(initial?: VisitorRequestWizardInitialData, branches?: Branch[], buildings?: Building[]) {
  const { submitVisitRequestUseCase, trackVisitRequestUseCase } = useAppDependencies()

  const [currentStep, setCurrentStep] = useState(0)
  const [formState, setFormState] = useState<VisitRequestFormState>(() => buildInitialFormState(initial))
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submissionStatus, setSubmissionStatus] = useState<SubmissionStatus>('idle')
  const [trackingId, setTrackingId] = useState<string | undefined>(undefined)
  const [confirmedFullName, setConfirmedFullName] = useState<string | undefined>(undefined)
  const [submissionError, setSubmissionError] = useState<string | undefined>(undefined)

  // Only ever set for a returning visitor's prefill (see
  // VisitorRequestWizardInitialData's comment above) — the invitation-
  // creation API silently discards any edited name for a contact it
  // recognizes, so the field is locked for the rest of this session rather
  // than letting the visitor type an edit that won't stick.
  const [primaryContactNameLocked] = useState(() => Boolean(initial?.primaryContact?.fullName))

  // Resolved the same way `submit` below resolves it for the real
  // request — matching branch name against the publicly listed branches —
  // so the Carried Items/Consent steps render (and validate against) the
  // same branch's Form Builder configuration the backend will actually
  // enforce, once that branch is known (step 1, Visit Info).
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
  // Carried Items' own admin-defined field groups (add-repeatable-field-groups),
  // rendered via `FieldGroupsSection` in `CarriedItemsStep` — same pattern as
  // Visitor/Vehicle Info's own groups above. Carried Items has no seeded
  // system group of its own, so there's nothing to exclude beyond
  // `!group.isSystem` (defensive, mirrors the other steps).
  const carriedItemsGroups = useMemo(
    () => findStepGroups(effectiveFormSteps, 'carried_items').filter((group) => !group.isSystem),
    [effectiveFormSteps],
  )
  const carriedItemsAllFields = useMemo(
    () => findStepFields(effectiveFormSteps, 'carried_items').filter((field) => !field.isSystem),
    [effectiveFormSteps],
  )
  // See `visitorInfoCustomFields`'s matching comment — excludes a grouped
  // field via its own `groupId`, not `group.fieldKeys`/`field.key` matching.
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
  // Branch-configured (form-builder) Purpose of Visit choices — the field's
  // own `options`, same pattern as `idProofOptions`/`vehicleTypeOptions`
  // below (make-id-proof-and-vehicle-type-configurable). `VisitInfoStep`
  // falls back to its hardcoded default list when this is empty, since
  // Purpose of Visit (unlike ID Proof/Vehicle Type) always renders
  // regardless of any active/inactive state.
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
  // Admin-authored (non-system) fields per step, passed to each step's
  // generic custom-fields section (add-generic-custom-field-support). Every
  // step now accepts new fields, not only the "fully configurable" ones.
  //
  // Visitor Info's own *admin-authored* field groups (add-repeatable-field-groups /
  // add-conditional-field-groups) render separately, through
  // `FieldGroupsSection` (see `VisitorInfoStep`) — a field assigned to one of
  // them (`field.groupId` set) is excluded here so it isn't also flattened
  // into the plain per-visitor custom-fields list. The seeded system group
  // ("visitors") is excluded from this list entirely — the backend won't
  // allow it to be made non-repeatable (it's a locked system group), so
  // there's no bespoke Visitor Details/"+ Add Visitor" UI for it any more;
  // an admin-created group (e.g. "Additional Visitors") is the supported
  // way to collect more than one visitor now, via `FieldGroupsSection`.
  const visitorInfoGroups = useMemo(
    () => findStepGroups(effectiveFormSteps, 'visitor_info').filter((group) => !group.isSystem),
    [effectiveFormSteps],
  )
  const visitorInfoAllFields = useMemo(
    () => findStepFields(effectiveFormSteps, 'visitor_info').filter((field) => !field.isSystem),
    [effectiveFormSteps],
  )
  // Excludes a field belonging to one of `visitorInfoGroups` (a non-system
  // group) via the field's own `groupId` — NOT via `group.fieldKeys`
  // matched against `field.key`, since a key can collide with a field on a
  // different group/step (mirrors VMSS_API's
  // `form_builder/validation.py::custom_fields_for_step`'s `groupId`-based
  // check; see `field-group-visibility.ts`'s `groupMemberFields` for the
  // matching fix on the submission side).
  const visitorInfoCustomFields = useMemo(() => {
    const nonSystemGroupIds = new Set(visitorInfoGroups.map((group) => group.id))
    return visitorInfoAllFields.filter((field) => field.groupId === null || !nonSystemGroupIds.has(field.groupId))
  }, [visitorInfoAllFields, visitorInfoGroups])
  const visitDetailsCustomFields = useMemo(
    () =>
      findStepFields(effectiveFormSteps, 'visit_details').filter(
        (field) => !field.isSystem || DISPLAY_ONLY_SYSTEM_FIELD_KEYS.has(field.key),
      ),
    [effectiveFormSteps],
  )
  // Every field the wire contract's invitation-level `customFields` bucket
  // covers (Visit Details, Carried Items, any custom step) — used to
  // resolve `formState.customFieldValues` into fieldId-keyed answers at
  // submit time.
  const invitationCustomFields = useMemo(() => findInvitationFields(effectiveFormSteps), [effectiveFormSteps])
  // Vehicle Info's own admin-defined field groups, rendered via
  // `FieldGroupsSection` in `VehicleInfoStep` — see the matching Visitor
  // Info comment above. The seeded "vehicles" system group is excluded; it
  // already has its own bespoke Add Vehicle UI.
  const vehicleInfoGroups = useMemo(
    () => findStepGroups(effectiveFormSteps, 'vehicle_info').filter((group) => !group.isSystem),
    [effectiveFormSteps],
  )
  const vehicleInfoAllFields = useMemo(
    () => findStepFields(effectiveFormSteps, 'vehicle_info').filter((field) => !field.isSystem),
    [effectiveFormSteps],
  )
  // See `visitorInfoCustomFields`'s matching comment.
  const vehicleInfoCustomFields = useMemo(() => {
    const nonSystemGroupIds = new Set(vehicleInfoGroups.map((group) => group.id))
    return vehicleInfoAllFields.filter((field) => field.groupId === null || !nonSystemGroupIds.has(field.groupId))
  }, [vehicleInfoAllFields, vehicleInfoGroups])
  // Ungrouped `file_upload` fields' keys, per bucket — backend's "inline
  // file-upload custom fields" contract (2026-09-24). See `submit` below,
  // and `custom-field-files.ts` for why each bucket needs its own
  // extraction (grouped file fields are unaffected, still handled by
  // `extractGroupFieldFiles`).
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

  // Eagerly (not at submit time) resolve a returning visitor's existing
  // ID-proof/photo URLs into real files, registered the same way a fresh
  // upload would be — FileUploadField then renders them as an existing-file
  // preview automatically once idProofFileRef/profileImageFileRef populate.
  // Eager, not lazy: the presigned URLs expire, and the wizard can sit open
  // for minutes before submit (design.md Decision 2). A fetch failure
  // (expired signature, network, or CORS) is swallowed — that field just
  // falls back to the normal empty fresh-upload control (Decision 3).
  const initialIdProofUrl = initial?.primaryContact?.idProofUrl
  const initialPhotoUrl = initial?.primaryContact?.photoUrl
  useEffect(() => {
    if (!initialIdProofUrl) return
    let cancelled = false
    fetchExistingFile(initialIdProofUrl, 'id-proof')
      .then(async (file) => {
        const fileRef = await uploadFile(file)
        if (cancelled) return
        setFormState((prev) => ({
          ...prev,
          primaryContact: { ...prev.primaryContact, idProofFileRef: fileRef, idProofFileName: file.name },
        }))
      })
      .catch(() => {
        // Leave idProofFileRef unset — the field renders as a normal,
        // empty fresh-upload control.
      })
    return () => {
      cancelled = true
    }
  }, [initialIdProofUrl])

  useEffect(() => {
    if (!initialPhotoUrl) return
    let cancelled = false
    fetchExistingFile(initialPhotoUrl, 'profile-photo')
      .then(async (file) => {
        const fileRef = await uploadFile(file)
        if (cancelled) return
        setFormState((prev) => ({
          ...prev,
          primaryContact: { ...prev.primaryContact, profileImageFileRef: fileRef, profileImageFileName: file.name },
        }))
      })
      .catch(() => {
        // Leave profileImageFileRef unset — the field renders as a normal,
        // empty fresh-upload control.
      })
    return () => {
      cancelled = true
    }
  }, [initialPhotoUrl])

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
    const stepErrors = {
      ...validateStep(activeSteps[currentStep]?.key, formState, requiredConsentKeys, visitorInfoFields, Boolean(branchId)),
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

  // Jumping to an already-completed step (e.g. via the sidebar) never needs
  // re-validation — only forward movement via goNext does.
  const goToStep = (step: number) => {
    if (step >= currentStep) return
    setErrors({})
    setCurrentStep(step)
  }

  const submit = async () => {
    // The backend requires `visitDetails.branchId`; a location that doesn't
    // match a listed branch (free-text fallback) leaves it undefined.
    if (!branchId) {
      setSubmissionError('Please select a valid location from the list before submitting.')
      setSubmissionStatus('error')
      return
    }
    const primaryContactIdProofFile = formState.primaryContact.idProofFileRef
      ? fileRegistry.current.get(formState.primaryContact.idProofFileRef)
      : undefined
    const primaryContactPhotoFile = formState.primaryContact.profileImageFileRef
      ? fileRegistry.current.get(formState.primaryContact.profileImageFileRef)
      : undefined
    const idProofMissing = visitorInfoFields.idProofActive && visitorInfoFields.idProofRequired && !primaryContactIdProofFile
    const photoMissing = visitorInfoFields.profilePhotoActive && visitorInfoFields.profilePhotoRequired && !primaryContactPhotoFile
    // A required ungrouped `file_upload` field (Visitor Info/Vehicle Info/
    // any other step) must have a real file for the primary contact, every
    // visitor, every vehicle, or the invitation itself — same "block before
    // the backend 422s" posture as the two checks above.
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
    if (idProofMissing || photoMissing || missingRequiredCustomFieldFile) {
      setSubmissionError('Something went wrong submitting your request. Please try again.')
      setSubmissionStatus('error')
      return
    }

    const visitorIdProofFiles = formState.additionalVisitors
      .map((visitor) => (visitor.idProofFileRef ? fileRegistry.current.get(visitor.idProofFileRef) : undefined))
      .filter((file): file is File => file !== undefined)
    // Always empty today — no wizard UI currently collects a profile photo
    // for anyone but the primary contact — but still wired through for
    // contract completeness (the backend part exists regardless).
    const visitorPhotoFiles = formState.additionalVisitors
      .map((visitor) => (visitor.profileImageFileRef ? fileRegistry.current.get(visitor.profileImageFileRef) : undefined))
      .filter((file): file is File => file !== undefined)

    // Admin-defined field groups' own `file_upload` fields (e.g. "id_upload"
    // on a custom "Additional Visitors" group) go through the same
    // fileRef-registry indirection as the fields above, but the backend
    // only accepts that answer as a multipart `groupFieldFiles[<groupKey>]`
    // part — never as a JSON value in `groupValues` (add-group-field-file-upload).
    const { sanitizedGroupValues, groupFieldFiles } = extractGroupFieldFiles(
      effectiveFormSteps,
      formState.groupValues,
      fileRegistry.current,
    )

    // Ungrouped `file_upload` fields go through their own bucket per where
    // they live — see `custom-field-files.ts`.
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
      const response = await submitVisitRequestUseCase.execute(
        toVisitRequest(
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
      // Best-effort: the create response never carries the primary contact's
      // name (design.md Decision 3), so look it up via the same public
      // tracking lookup the visitor-track-request capability uses. A
      // failure here doesn't affect the already-successful submission.
      trackVisitRequestUseCase
        .execute(response.trackingId)
        .then((lookup) => setConfirmedFullName(lookup.primaryContactFullName))
        .catch(() => {
          // Leave confirmedFullName unset — the success screen just omits it.
        })
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
    confirmedFullName,
    submissionError,
    submit,
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
    primaryContactNameLocked,
    vehicleInfoGroups,
    vehicleInfoAllFields,
  }
}
