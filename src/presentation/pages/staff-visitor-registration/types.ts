import { toConsentAnswers, toFieldAnswers } from '../../components/dynamic-fields/field-answers'
import { toGroupAnswers } from '../../components/dynamic-fields/field-group-visibility'
import type { EffectiveFormStep, FormField } from '../../../domain/entities/form-builder-schema'
import type { StaffVisitRequest } from '../../../domain/entities/staff-visit-request-schema'
import type {
  CarriedItemsFormState,
  ConsentFormState,
  CustomFieldValues,
  GroupValues,
  RegistrationType,
  VehicleFormEntry,
  VisitInfoFormState,
} from '../visitor-request/types'

export interface StaffVisitorFormEntry {
  fullName: string
  email: string
  phone: string
  visitorCategory: string
  preferredContactMethod?: 'email' | 'sms'
  idProofType: string
  idProofFileRef?: string
  idProofFileName?: string
  profileImageFileRef?: string
  profileImageFileName?: string
  // See visitor-request/types.ts's `VisitorFormEntry.customFieldValues`.
  customFieldValues: CustomFieldValues
}

export function createEmptyStaffVisitorFormEntry(): StaffVisitorFormEntry {
  return {
    fullName: '',
    email: '',
    phone: '',
    visitorCategory: '',
    // Matches the Preferred Contact Method toggle's default visual selection.
    preferredContactMethod: 'email',
    idProofType: '',
    customFieldValues: {},
  }
}

export interface StaffVisitRequestFormState {
  registrationType: RegistrationType
  primaryContact: StaffVisitorFormEntry
  additionalVisitors: StaffVisitorFormEntry[]
  visitInfo: VisitInfoFormState
  carriedItems: CarriedItemsFormState
  vehicles: VehicleFormEntry[]
  consent: ConsentFormState
  customFieldValues: CustomFieldValues
  groupValues: GroupValues
}

export function createInitialStaffFormState(): StaffVisitRequestFormState {
  return {
    registrationType: 'individual',
    primaryContact: createEmptyStaffVisitorFormEntry(),
    additionalVisitors: [],
    visitInfo: {
      purpose: '',
      preferredDate: '',
      preferredTime: '',
      location: '',
      building: '',
    },
    carriedItems: { categories: [], description: '' },
    vehicles: [],
    consent: {},
    customFieldValues: {},
    groupValues: {},
  }
}

// Neither `primaryContact` nor a `visitors[]` entry carries its own
// `customFields` — see visitor-request/types.ts's matching `toVisitor`.
function toStaffVisitor(entry: StaffVisitorFormEntry) {
  return {
    fullName: entry.fullName,
    email: entry.email,
    phone: entry.phone,
    preferredContactMethod: entry.preferredContactMethod,
    // See visitor-request/types.ts's matching comment.
    idProofType: entry.idProofType || undefined,
  }
}

// See visitor-request/types.ts's matching `VisitRequestWireContext`.
export interface StaffVisitRequestWireContext {
  visitorInfoFields: FormField[]
  vehicleInfoFields: FormField[]
  invitationFields: FormField[]
  consentFields: FormField[]
  steps: EffectiveFormStep[]
}

// Maps wizard form state onto the `payload` wire contract for POST /invitations
// (identical contract to POST /registrations/walk-in, see visitor-request/types.ts).
// `location`/`building` aren't part of that contract and are dropped here; the
// primary contact's visitor category becomes the invitation-level
// `visitorCategoryId` (one category per invitation, not per visitor). ID-proof
// files travel separately, see use-staff-visitor-registration-wizard.
export function toStaffVisitRequest(formState: StaffVisitRequestFormState, context: StaffVisitRequestWireContext): StaffVisitRequest {
  const visitors = formState.additionalVisitors.map(toStaffVisitor)
  const vehicles = formState.vehicles.map((vehicle) => ({
    vehicleType: vehicle.vehicleType,
    licensePlate: vehicle.licensePlate,
    makeModel: vehicle.makeModel,
    color: vehicle.color,
  }))
  // See visitor-request/types.ts's matching comment — every custom-field
  // answer in the request shares this single top-level array.
  const customFields = [
    ...toFieldAnswers(formState.customFieldValues, context.invitationFields),
    ...toFieldAnswers(formState.primaryContact.customFieldValues, context.visitorInfoFields),
    ...formState.additionalVisitors.flatMap((visitor) => toFieldAnswers(visitor.customFieldValues, context.visitorInfoFields)),
    ...formState.vehicles.flatMap((vehicle) => toFieldAnswers(vehicle.customFieldValues, context.vehicleInfoFields)),
  ]
  const groups = toGroupAnswers(context.steps, formState.groupValues)

  return {
    registrationType: formState.registrationType,
    visitorCategoryId: formState.primaryContact.visitorCategory,
    primaryContact: toStaffVisitor(formState.primaryContact),
    // See visitor-request/types.ts's matching comment on omitting empty
    // defaultable arrays — `consents` is the one exception, always sent.
    visitors: visitors.length > 0 ? visitors : undefined,
    visitDetails: {
      purposeOfVisit: formState.visitInfo.purpose,
      preferredVisitDate: formState.visitInfo.preferredDate,
      preferredVisitTime: formState.visitInfo.preferredTime,
    },
    carriedItems:
      formState.carriedItems.categories.length > 0 || formState.carriedItems.description
        ? { items: formState.carriedItems.categories, itemDescription: formState.carriedItems.description }
        : undefined,
    vehicles: vehicles.length > 0 ? vehicles : undefined,
    consents: toConsentAnswers(formState.consent, context.consentFields),
    customFields: customFields.length > 0 ? customFields : undefined,
    groups: groups.length > 0 ? groups : undefined,
  }
}
