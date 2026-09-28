import type { DynamicFieldValue } from '../../components/dynamic-fields/DynamicField'
import { toConsentAnswers, toFieldAnswers } from '../../components/dynamic-fields/field-answers'
import { toGroupAnswers } from '../../components/dynamic-fields/field-group-visibility'
import type { Vehicle } from '../../../domain/entities/vehicle-schema'
import type { Visitor } from '../../../domain/entities/visitor-schema'
import type { VisitorCategory } from '../../../domain/entities/visitor-category-schema'
import type { VisitRequest } from '../../../domain/entities/visit-request-schema'
import type { EffectiveFormStep, FormField } from '../../../domain/entities/form-builder-schema'

export type RegistrationType = 'individual' | 'group'

// Distinguishes "still loading" from "loaded and empty" from "failed" —
// collapsing all three into `VisitorCategory[] | undefined` is what let a
// hardcoded fallback list of fake, non-UUID category ids get silently
// offered and submitted (fix-visitor-category-invalid-id-fallback).
export interface VisitorCategoriesFieldState {
  status: 'loading' | 'error' | 'loaded'
  categories: VisitorCategory[]
}

// Wizard-internal vehicle state — same shape as the wire contract's
// `Vehicle`, except `customFieldValues` stays a flat, key-indexed map here
// (matching every other step's internal state) rather than the wire
// contract's fieldId-indexed `customFields` array; only converted at
// submission time, see `toVisitRequest`.
export interface VehicleFormEntry extends Vehicle {
  customFieldValues: Record<string, DynamicFieldValue>
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
  vehicles: VehicleFormEntry[]
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

// Neither `primaryContact` nor a `visitors[]` entry carries its own
// `customFields` on the wire — every Visitor Info answer, for the primary
// contact or any additional visitor, flows through the request's single
// top-level `customFields` array instead, see `toVisitRequest`.
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
  }
}

/** Every field list `toVisitRequest` needs to resolve `key`-based wizard
 * state into the wire contract's `fieldId`-based shape. */
export interface VisitRequestWireContext {
  visitorInfoFields: FormField[]
  vehicleInfoFields: FormField[]
  invitationFields: FormField[]
  consentFields: FormField[]
  steps: EffectiveFormStep[]
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
export function toVisitRequest(formState: VisitRequestFormState, context: VisitRequestWireContext): VisitRequest {
  const visitors = formState.additionalVisitors.map(toVisitor)
  const vehicles = formState.vehicles.map((vehicle) => ({
    vehicleType: vehicle.vehicleType,
    licensePlate: vehicle.licensePlate,
    makeModel: vehicle.makeModel,
    color: vehicle.color,
  }))
  // Every custom-field answer in the request — invitation-level (Visit
  // Details/Carried Items/a custom step), the primary contact's and every
  // additional visitor's Visitor Info answers, and every vehicle's Vehicle
  // Info answers — shares this single top-level array; neither `visitors[]`
  // nor `vehicles[]` carries its own `customFields` slot.
  const customFields = [
    ...toFieldAnswers(formState.customFieldValues, context.invitationFields),
    ...toFieldAnswers(formState.primaryContact.customFieldValues, context.visitorInfoFields),
    ...formState.additionalVisitors.flatMap((visitor) => toFieldAnswers(visitor.customFieldValues, context.visitorInfoFields)),
    ...formState.vehicles.flatMap((vehicle) => toFieldAnswers(vehicle.customFieldValues, context.vehicleInfoFields)),
  ]
  const groups = toGroupAnswers(context.steps, formState.groupValues)
  const consents = toConsentAnswers(formState.consent, context.consentFields)

  return {
    registrationType: formState.registrationType,
    visitorCategoryId: formState.primaryContact.visitorCategory,
    primaryContact: toVisitor(formState.primaryContact),
    // `visitors`/`vehicles`/`carriedItems`/`customFields`/`groups` all
    // default on the backend (`Field(default_factory=...)`) — omitted
    // entirely (`JSON.stringify` drops an `undefined` value) rather than
    // sent as an explicit empty value, when there's nothing to send.
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
    // Backend now defaults `consents` to `[]` when omitted (matches
    // `visitors`/`vehicles`/`customFields`/`groups` above) — safe to drop
    // entirely when there's nothing to send, same pattern as those.
    consents: consents.length > 0 ? consents : undefined,
    customFields: customFields.length > 0 ? customFields : undefined,
    groups: groups.length > 0 ? groups : undefined,
  }
}
