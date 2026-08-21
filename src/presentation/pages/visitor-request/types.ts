import type { Vehicle } from '../../../domain/entities/vehicle-schema'
import type { Visitor } from '../../../domain/entities/visitor-schema'
import type { VisitRequest } from '../../../domain/entities/visit-request-schema'

export type RegistrationType = 'individual' | 'group'

export interface VisitorFormEntry {
  fullName: string
  email: string
  phone: string
  address: string
  visitorCategory: string
  preferredContactMethod?: 'email' | 'sms'
  idProofType: string
  idProofFileRef?: string
  idProofFileName?: string
  profileImageFileRef?: string
  profileImageFileName?: string
}

export function createEmptyVisitorFormEntry(): VisitorFormEntry {
  return {
    fullName: '',
    email: '',
    phone: '',
    address: '',
    visitorCategory: '',
    idProofType: '',
  }
}

export interface VisitInfoFormState {
  purpose: string
  hostNameOrEmail: string
  preferredDate: string
  preferredTime: string
  expectedDuration: string
  location: string
  building: string
  department: string
  notes: string
}

export interface CarriedItemsFormState {
  categories: string[]
  description: string
}

export interface ConsentFormState {
  agreedTerms: boolean
  agreedDataUse: boolean
  agreedSafety: boolean
}

export interface VisitRequestFormState {
  registrationType: RegistrationType
  primaryContact: VisitorFormEntry
  additionalVisitors: VisitorFormEntry[]
  visitInfo: VisitInfoFormState
  carriedItems: CarriedItemsFormState
  vehicles: Vehicle[]
  consent: ConsentFormState
}

export function createInitialFormState(): VisitRequestFormState {
  return {
    registrationType: 'individual',
    primaryContact: createEmptyVisitorFormEntry(),
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

export function toVisitor(entry: VisitorFormEntry): Visitor {
  return {
    fullName: entry.fullName,
    email: entry.email,
    phone: entry.phone,
    preferredContactMethod: entry.preferredContactMethod,
    idProofType: entry.idProofType,
  }
}

// Maps wizard form state onto the `payload` wire contract for
// POST /registrations/walk-in. `location`/`building`/address/visitorCategory/
// profile image aren't part of that contract (yet) and are dropped here; ID-proof
// files travel separately as multipart file fields, see use-visitor-request-wizard.
export function toVisitRequest(formState: VisitRequestFormState): VisitRequest {
  return {
    registrationType: formState.registrationType,
    primaryContact: toVisitor(formState.primaryContact),
    visitors: formState.additionalVisitors.map(toVisitor),
    visitDetails: {
      purposeOfVisit: formState.visitInfo.purpose,
      hostNameOrEmail: formState.visitInfo.hostNameOrEmail,
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

export const WIZARD_STEPS = [
  'Visitor Info',
  'Visit Info',
  'Carried Items',
  'Vehicle Info',
  'Consent Agreement',
  'Review & Confirm',
] as const
