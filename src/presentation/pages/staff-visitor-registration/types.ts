import type { Vehicle } from '../../../domain/entities/vehicle-schema'
import type { StaffVisitRequest } from '../../../domain/entities/staff-visit-request-schema'
import type { CarriedItemsFormState, ConsentFormState, CustomFieldValues, RegistrationType, VisitInfoFormState } from '../visitor-request/types'

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
  vehicles: Vehicle[]
  consent: ConsentFormState
  customFieldValues: CustomFieldValues
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
      expectedDuration: '',
      location: '',
      building: '',
      notes: '',
    },
    carriedItems: { categories: [], description: '' },
    vehicles: [],
    consent: {},
    customFieldValues: {},
  }
}

function toStaffVisitor(entry: StaffVisitorFormEntry) {
  return {
    fullName: entry.fullName,
    email: entry.email,
    phone: entry.phone,
    preferredContactMethod: entry.preferredContactMethod,
    idProofType: entry.idProofType,
    customFieldValues: entry.customFieldValues,
  }
}

// Maps wizard form state onto the `payload` wire contract for POST /invitations
// (identical contract to POST /registrations/walk-in, see visitor-request/types.ts).
// `location`/`building` aren't part of that contract and are dropped here; the
// primary contact's visitor category becomes the invitation-level
// `visitorCategoryId` (one category per invitation, not per visitor). ID-proof
// files travel separately, see use-staff-visitor-registration-wizard.
export function toStaffVisitRequest(formState: StaffVisitRequestFormState): StaffVisitRequest {
  return {
    registrationType: formState.registrationType,
    visitorCategoryId: formState.primaryContact.visitorCategory,
    primaryContact: toStaffVisitor(formState.primaryContact),
    visitors: formState.additionalVisitors.map(toStaffVisitor),
    visitDetails: {
      purposeOfVisit: formState.visitInfo.purpose,
      preferredVisitDate: formState.visitInfo.preferredDate,
      preferredVisitTime: formState.visitInfo.preferredTime,
      expectedDuration: formState.visitInfo.expectedDuration,
      additionalNotes: formState.visitInfo.notes,
    },
    carriedItems: {
      items: formState.carriedItems.categories,
      itemDescription: formState.carriedItems.description,
    },
    vehicles: formState.vehicles,
    consents: formState.consent,
    customFieldValues: formState.customFieldValues,
  }
}
