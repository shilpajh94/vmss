import type { Vehicle } from '../../../domain/entities/vehicle-schema'
import type { StaffVisitRequest } from '../../../domain/entities/staff-visit-request-schema'
import type { CarriedItemsFormState, ConsentFormState, RegistrationType, VisitInfoFormState } from '../visitor-request/types'

export interface StaffVisitorFormEntry {
  fullName: string
  email: string
  phone: string
  visitorCategory: string
  preferredContactMethod?: 'email' | 'sms'
  idProofType: string
  idProofFileRef?: string
  idProofFileName?: string
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
}

export function createInitialStaffFormState(): StaffVisitRequestFormState {
  return {
    registrationType: 'individual',
    primaryContact: createEmptyStaffVisitorFormEntry(),
    additionalVisitors: [],
    visitInfo: {
      purpose: '',
      hostNameOrEmail: '',
      hostId: '',
      preferredDate: '',
      preferredTime: '',
      expectedDuration: '',
      location: '',
      building: '',
      department: '',
      notes: '',
    },
    carriedItems: { categories: [], description: '' },
    vehicles: [],
    consent: { agreedTerms: false, agreedDataUse: false, agreedSafety: false },
  }
}

function toStaffVisitor(entry: StaffVisitorFormEntry) {
  return {
    fullName: entry.fullName,
    email: entry.email,
    phone: entry.phone,
    preferredContactMethod: entry.preferredContactMethod,
    idProofType: entry.idProofType,
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
      hostNameOrEmail: formState.visitInfo.hostNameOrEmail,
      hostId: formState.visitInfo.hostId,
      preferredVisitDate: formState.visitInfo.preferredDate,
      preferredVisitTime: formState.visitInfo.preferredTime,
      expectedDuration: formState.visitInfo.expectedDuration,
      departmentToVisit: formState.visitInfo.department,
      additionalNotes: formState.visitInfo.notes,
    },
    carriedItems: {
      items: formState.carriedItems.categories,
      itemDescription: formState.carriedItems.description,
    },
    vehicles: formState.vehicles,
    consents: {
      termsAccepted: formState.consent.agreedTerms,
      dataProcessingAccepted: formState.consent.agreedDataUse,
      safetyGuidelinesAccepted: formState.consent.agreedSafety,
    },
  }
}

export const STAFF_WIZARD_STEPS = [
  'Visitor Info',
  'Visit Info',
  'Carried Items',
  'Vehicle Info',
  'Consent Agreement',
  'Review & Confirm',
] as const
