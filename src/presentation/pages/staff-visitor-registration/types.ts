import type { Vehicle } from '../../../domain/entities/vehicle-schema'
import type { StaffVisitRequest } from '../../../domain/entities/staff-visit-request-schema'
import type { CarriedItemsFormState, ConsentFormState, RegistrationType, VisitInfoFormState } from '../visitor-request/types'

export interface StaffVisitorFormEntry {
  fullName: string
  email: string
  phone: string
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
    idProofFileRef: entry.idProofFileRef,
  }
}

export function toStaffVisitRequest(formState: StaffVisitRequestFormState): StaffVisitRequest {
  return {
    registrationType: formState.registrationType,
    primaryContact: toStaffVisitor(formState.primaryContact),
    additionalVisitors: formState.additionalVisitors.map(toStaffVisitor),
    visitInfo: formState.visitInfo,
    carriedItems: formState.carriedItems,
    vehicles: formState.vehicles,
    consent: formState.consent,
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
