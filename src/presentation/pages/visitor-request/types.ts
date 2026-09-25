import type { DynamicFieldValue } from '../../components/dynamic-fields/DynamicField'
import type { Vehicle } from '../../../domain/entities/vehicle-schema'
import type { Visitor } from '../../../domain/entities/visitor-schema'
import type { VisitorCategory } from '../../../domain/entities/visitor-category-schema'
import type { VisitRequest } from '../../../domain/entities/visit-request-schema'

export type RegistrationType = 'individual' | 'group'

// Distinguishes "still loading" from "loaded and empty" from "failed" —
// collapsing all three into `VisitorCategory[] | undefined` is what let a
// hardcoded fallback list of fake, non-UUID category ids get silently
// offered and submitted (fix-visitor-category-invalid-id-fallback).
export interface VisitorCategoriesFieldState {
  status: 'loading' | 'error' | 'loaded'
  categories: VisitorCategory[]
}

export interface VisitorFormEntry {
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
  // This visitor's own answers for any admin-authored Visitor Info field
  // (add-generic-custom-field-support) — independent of every other
  // visitor's answer for the same field.
  customFieldValues: Record<string, DynamicFieldValue>
}

export function createEmptyVisitorFormEntry(): VisitorFormEntry {
  return {
    fullName: '',
    email: '',
    phone: '',
    visitorCategory: '',
    // Matches the Preferred Contact Method toggle's default visual selection
    // (see VisitorFieldsForm's `value.preferredContactMethod ?? 'email'`) —
    // without this, a fresh entry's method is `undefined`, which fails
    // validation with no visible error and makes "Next" appear dead.
    preferredContactMethod: 'email',
    idProofType: '',
    customFieldValues: {},
  }
}

export interface VisitInfoFormState {
  purpose: string
  preferredDate: string
  preferredTime: string
  location: string
  building: string
}

export interface CarriedItemsFormState {
  categories: string[]
  description: string
}

// Dynamic, branch-configured consent-key -> accepted, keyed by whatever the
// resolved branch's published Consent Agreement step currently declares
// (form-builder) — not a fixed `agreedTerms`/`agreedDataUse`/`agreedSafety`
// shape. See ConsentStep, which renders one checkbox per active field.
export type ConsentFormState = Record<string, boolean>

// Flat, keyed by field key — answers for every admin-authored field whose
// step has no per-entity structure of its own: Visit Details, Carried
// Items (beyond its seeded `items`/`item_description` fields), and any
// custom step (add-generic-custom-field-support). One shared bucket
// because the wire contract's `customFieldValues` is itself one flat map
// at the request's top level; Visitor Info/Vehicle Info fields go on
// `VisitorFormEntry`/`Vehicle` instead, since those are per-visitor/
// per-vehicle. Consent Agreement fields are excluded — they flow through
// `consent` below regardless of whether they're seeded or admin-authored.
export type CustomFieldValues = Record<string, DynamicFieldValue>

// One custom (admin-defined) repeatable field group's current instances,
// keyed by the group's own `key` — the wizard-side counterpart of the wire
// contract's `groupValues` (add-repeatable-field-groups). Every instance is
// a flat answer map keyed by that group's field keys, matching how
// `RepeatableFieldGroup` reads/writes them via `CustomFieldsSection`.
export type GroupValues = Record<string, Record<string, DynamicFieldValue>[]>

export interface VisitRequestFormState {
  registrationType: RegistrationType
  primaryContact: VisitorFormEntry
  additionalVisitors: VisitorFormEntry[]
  visitInfo: VisitInfoFormState
  carriedItems: CarriedItemsFormState
  vehicles: Vehicle[]
  consent: ConsentFormState
  customFieldValues: CustomFieldValues
  groupValues: GroupValues
}

export function createInitialFormState(): VisitRequestFormState {
  return {
    registrationType: 'individual',
    primaryContact: createEmptyVisitorFormEntry(),
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

export function toVisitor(entry: VisitorFormEntry): Visitor {
  return {
    fullName: entry.fullName,
    email: entry.email,
    phone: entry.phone,
    preferredContactMethod: entry.preferredContactMethod,
    // Omitted rather than sent as `''` when ID Proof Type isn't
    // active/required for this branch and the visitor left it blank — the
    // backend validates any *present* value against its known ID proof
    // types and rejects an empty string as unrecognized.
    idProofType: entry.idProofType || undefined,
    customFieldValues: entry.customFieldValues,
  }
}

// Maps wizard form state onto the `payload` wire contract for
// POST /registrations/walk-in. `location`/`building`/profile image
// aren't part of that contract (yet) and are dropped here; the primary
// contact's visitor category becomes the invitation-level `visitorCategoryId`
// (the wire contract has one category per invitation, not per visitor). ID-proof
// files travel separately as multipart file fields, see use-visitor-request-wizard.
// `hostId`/`hostNameOrEmail`/`departmentToVisit` are no longer collected by
// the wizard at all (role-based-invitation-workflow) — omitted entirely
// rather than sent empty; the API resolves the invitation's owning role by
// default and reception fills in the department later.
export function toVisitRequest(formState: VisitRequestFormState): VisitRequest {
  return {
    registrationType: formState.registrationType,
    visitorCategoryId: formState.primaryContact.visitorCategory,
    primaryContact: toVisitor(formState.primaryContact),
    visitors: formState.additionalVisitors.map(toVisitor),
    visitDetails: {
      purposeOfVisit: formState.visitInfo.purpose,
      preferredVisitDate: formState.visitInfo.preferredDate,
      preferredVisitTime: formState.visitInfo.preferredTime,
    },
    carriedItems: {
      items: formState.carriedItems.categories,
      itemDescription: formState.carriedItems.description,
    },
    vehicles: formState.vehicles,
    consents: formState.consent,
    customFieldValues: formState.customFieldValues,
    groupValues: formState.groupValues,
  }
}
