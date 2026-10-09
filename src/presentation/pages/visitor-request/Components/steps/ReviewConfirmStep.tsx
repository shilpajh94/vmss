import type { ReactNode } from 'react'
import type {
  CarriedItemsFormState,
  ConsentFormState,
  CustomFieldValues,
  GroupValues,
  RegistrationType,
  VehicleFormEntry,
  VisitInfoFormState,
} from '../../types'
import type { EffectiveFormFieldGroup, EffectiveFormStep, FormField } from '../../../../../domain/entities/form-builder-schema'
import type { VisitorCategory } from '../../../../../domain/entities/visitor-category-schema'
import { Spinner } from '../../../../components/ui/LoadingState'
import { FileTextIcon } from '../../../../components/icons'
import { getFilePreviewKind } from '../../../../utils/file-preview-kind'
import { prettifyKey } from '../../../../utils/prettify-key'
import { formatDynamicFieldValue } from '../../../../components/dynamic-fields/format-dynamic-field-value'
import { isCanonicalStepKey } from '../../registration-wizard-steps'
import { isGroupVisible, resolveGroupFlatValues } from '../../../../components/dynamic-fields/field-group-visibility'
import type { DynamicFieldFileValue, DynamicFieldValue } from '../../../../components/dynamic-fields/DynamicField'

export type SubmissionStatus = 'idle' | 'submitting' | 'success' | 'error'

export interface ReviewVisitorSummary {
  fullName: string
  email: string
  phone: string
  visitorCategory?: string
  preferredContactMethod?: 'email' | 'sms'
  idProofType: string
  idProofFileRef?: string
  idProofFileName?: string
  profileImageFileRef?: string
  profileImageFileName?: string
  /** The primary contact's own answers to admin-authored Visitor Info
   * fields — needed so a group's `visibilityCondition` watching one of them
   * can be resolved the same way `VisitorInfoStep` resolves it. */
  customFieldValues?: Record<string, DynamicFieldValue>
}

export interface ReviewableFormState {
  registrationType: RegistrationType
  primaryContact: ReviewVisitorSummary
  additionalVisitors: ReviewVisitorSummary[]
  visitInfo: VisitInfoFormState
  carriedItems: CarriedItemsFormState
  vehicles: VehicleFormEntry[]
  consent: ConsentFormState
  customFieldValues: CustomFieldValues
  groupValues: GroupValues
}

interface ReviewConfirmStepProps {
  formState: ReviewableFormState
  status: SubmissionStatus
  trackingId?: string
  /** The primary contact's confirmed name of record, looked up after a
   * successful submission (design.md Decision 3) — may differ from what
   * was submitted for a contact the server already knows, and may briefly
   * be undefined while that lookup is still in flight. */
  confirmedFullName?: string
  errorMessage?: string
  visitorCategories?: VisitorCategory[]
  getFilePreviewUrl?: (fileRef?: string) => string | undefined
  /** Active Vehicle Info custom fields, for labeling each vehicle's custom
   * field values in the summary below (form-builder). */
  vehicleCustomFields?: FormField[]
  /** Active Carried Items custom fields, for labeling values pulled from
   * `formState.customFieldValues` (form-builder). */
  carriedItemsCustomFields?: FormField[]
  /** Visitor Info's own admin-defined field groups (e.g. an "Additional
   * Visitors" group) plus every field they reference, so group instances —
   * otherwise invisible here, since they live in `formState.groupValues`,
   * not `additionalVisitors` — can be summarized below (add-repeatable-field-groups). */
  visitorInfoGroups?: EffectiveFormFieldGroup[]
  visitorInfoAllFields?: FormField[]
  /** Same as above, for Vehicle Info's own field groups. */
  vehicleInfoGroups?: EffectiveFormFieldGroup[]
  vehicleInfoAllFields?: FormField[]
  /** Same as above, for Carried Items' own field groups (e.g. a repeatable
   * "Items Carried" group). */
  carriedItemsGroups?: EffectiveFormFieldGroup[]
  carriedItemsAllFields?: FormField[]
  /** Active Visitor Info custom fields (ungrouped), answered per visitor —
   * shown under each visitor in the Visitor Info summary. */
  visitorInfoCustomFields?: FormField[]
  /** Active Visit Info custom fields, read from `formState.customFieldValues`. */
  visitDetailsCustomFields?: FormField[]
  /** Every active step — used to summarize Visit Info's own field groups and
   * every admin-created (non-canonical) step's fields and groups. */
  steps?: EffectiveFormStep[]
  onBack: () => void
  onSubmit: () => void
  onGoHome?: () => void
  homeLabel?: string
}

function SummarySection({ title, rows }: { title: string; rows: [string, ReactNode][] }) {
  return (
    <div className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-4 shadow-[0_4px_8px_rgba(15,23,42,0.03)] md:p-6">
      <h4 className="font-display text-base font-semibold text-text">{title}</h4>
      <dl className="grid grid-cols-1 gap-4 text-body sm:grid-cols-2">
        {rows.map(([label, value], index) => (
          <div key={`${label}-${index}`} className="flex flex-col gap-1">
            <dt className="text-caption text-text-muted">{label}</dt>
            <dd className="text-text">{value || '—'}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

function FilePreviewCell({ fileName, previewUrl }: { fileName?: string; previewUrl?: string }) {
  if (!fileName) return 'Not uploaded'
  if (!previewUrl) return fileName
  const kind = getFilePreviewKind(fileName)
  return (
    <a href={previewUrl} target="_blank" rel="noreferrer" className="flex items-center gap-2">
      {kind === 'image' && <img src={previewUrl} alt={fileName} className="size-10 shrink-0 rounded-lg border border-border object-cover" />}
      {kind === 'pdf' && (
        <span className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-border bg-danger/10 text-danger">
          <FileTextIcon className="size-5" />
        </span>
      )}
      <span className="text-text underline">{fileName}</span>
    </a>
  )
}

/** Renders one admin-configured field's submitted value for a summary row —
 * `formatDynamicFieldValue` as plain text, except a `file_upload` field gets
 * the same clickable thumbnail/link treatment (`FilePreviewCell`) the
 * primary/additional visitor's hardcoded ID Proof/Profile Image rows above
 * already get, instead of just its raw file name. */
function DynamicFieldValueCell({
  field,
  value,
  getFilePreviewUrl,
}: {
  field: FormField
  value: DynamicFieldValue
  getFilePreviewUrl?: (fileRef?: string) => string | undefined
}): ReactNode {
  if (field.fieldType === 'file_upload') {
    const fileValue = value as DynamicFieldFileValue | undefined
    return <FilePreviewCell fileName={fileValue?.fileName} previewUrl={getFilePreviewUrl?.(fileValue?.fileRef)} />
  }
  return formatDynamicFieldValue(field, value)
}

/** One `SummarySection` per visible field group (add-repeatable-field-groups
 * / add-conditional-field-groups) — mirrors `FieldGroupsSection`'s
 * gating/instance logic, but read-only. Each repeatable group gets one row
 * per instance per field; a non-repeatable group's single instance lives at
 * `groupValues[key][0]`, matching how `FieldGroupsSection` stores it. */
function GroupSummarySections({
  groups,
  fields,
  groupValues,
  flatValues,
  getFilePreviewUrl,
}: {
  groups: EffectiveFormFieldGroup[]
  fields: FormField[]
  groupValues: GroupValues
  flatValues: Record<string, DynamicFieldValue>
  getFilePreviewUrl?: (fileRef?: string) => string | undefined
}) {
  const orderedGroups = [...groups].sort((a, b) => a.orderIndex - b.orderIndex)

  return (
    <>
      {orderedGroups.map((group) => {
        if (!isGroupVisible(group.visibilityCondition, flatValues)) return null

        const groupFields = group.fieldKeys
          .map((fieldKey) => fields.find((field) => field.key === fieldKey))
          .filter((field): field is FormField => field !== undefined)
        const instances = groupValues[group.key] ?? []

        if (instances.length === 0) return null

        return (
          <SummarySection
            key={group.id}
            title={group.isRepeatable ? `${group.name} (${instances.length})` : group.name}
            rows={instances.flatMap((instance, index) =>
              groupFields.map((field): [string, ReactNode] => [
                group.isRepeatable ? `${group.name} ${index + 1} — ${field.label}` : field.label,
                <DynamicFieldValueCell key={field.key} field={field} value={instance[field.key]} getFilePreviewUrl={getFilePreviewUrl} />,
              ]),
            )}
          />
        )
      })}
    </>
  )
}

export function ReviewConfirmStep({
  formState,
  status,
  trackingId,
  confirmedFullName,
  errorMessage,
  visitorCategories,
  getFilePreviewUrl,
  vehicleCustomFields = [],
  carriedItemsCustomFields = [],
  visitorInfoGroups = [],
  visitorInfoAllFields = [],
  vehicleInfoGroups = [],
  vehicleInfoAllFields = [],
  carriedItemsGroups = [],
  carriedItemsAllFields = [],
  visitorInfoCustomFields = [],
  visitDetailsCustomFields = [],
  steps = [],
  onBack,
  onSubmit,
  onGoHome,
  homeLabel = 'Back to Home',
}: ReviewConfirmStepProps) {
  if (status === 'success') {
    return (
      <div className="flex flex-col items-center gap-3 rounded-lg border border-success bg-surface p-5 text-center md:p-8">
        <h3 className="text-h3 text-text">Request Submitted</h3>
        <p className="text-body text-text-muted">Your visit request has been received. You can reference this tracking ID for any follow-up.</p>
        <p className="text-h2 text-primary">{trackingId}</p>
        {confirmedFullName && <p className="text-body text-text-muted">Registered as: {confirmedFullName}</p>}
        {onGoHome && (
          <button
            type="button"
            onClick={onGoHome}
            title={homeLabel}
            className="mt-2 cursor-pointer rounded-lg bg-primary px-6 py-3 text-body font-semibold text-white transition-colors hover:opacity-90"
          >
            {homeLabel}
          </button>
        )}
      </div>
    )
  }

  const visitors = [formState.primaryContact, ...formState.additionalVisitors]
  const visitDetailsStep = steps.find((step) => step.key === 'visit_details')
  const customSteps = steps.filter((step) => !isCanonicalStepKey(step.key))

  const visitorCategoryName = (id: string) => visitorCategories?.find((category) => category.id === id)?.name ?? id
  const preferredContactMethodLabel = (method?: 'email' | 'sms') => (method === 'sms' ? 'SMS' : method === 'email' ? 'Email' : '')

  // Matches the seed values each step itself resolves group conditions
  // against (see VisitorInfoStep/VehicleInfoStep) — a group's condition can
  // only watch a field on its own step.
  const visitorGroupFlatValues = resolveGroupFlatValues(visitorInfoGroups, formState.groupValues, {
    registration_type: formState.registrationType,
    ...formState.primaryContact.customFieldValues,
  })
  const vehicleGroupFlatValues = resolveGroupFlatValues(vehicleInfoGroups, formState.groupValues, {})
  const carriedItemsGroupFlatValues = resolveGroupFlatValues(carriedItemsGroups, formState.groupValues, formState.customFieldValues)

  return (
    <div className="flex flex-col gap-6">
      <h3 className="text-h3 text-text">Review &amp; Confirm</h3>

      {status === 'error' && (
        <div className="rounded-lg border border-danger bg-surface p-4 text-body text-danger">
          {errorMessage ?? 'Something went wrong submitting your request. Please try again.'}
        </div>
      )}

      <SummarySection
        title={`Visitor Info (${formState.registrationType === 'group' ? `${visitors.length} visitors` : 'Individual'})`}
        rows={visitors.flatMap((visitor, index) => {
          const rows: [string, ReactNode][] = [
            [visitors.length > 1 ? `Visitor ${index + 1} Name` : 'Full Name', visitor.fullName],
            ['Email', visitor.email],
            ['Phone', visitor.phone],
          ]
          if (visitor.preferredContactMethod) {
            rows.push(['Preferred Contact Method', preferredContactMethodLabel(visitor.preferredContactMethod)])
          }
          rows.push(['Visitor Category', visitor.visitorCategory ? visitorCategoryName(visitor.visitorCategory) : ''])
          rows.push(['ID Proof', visitor.idProofType])
          rows.push([
            'ID Proof File',
            <FilePreviewCell key="idProofFile" fileName={visitor.idProofFileName} previewUrl={getFilePreviewUrl?.(visitor.idProofFileRef)} />,
          ])
          rows.push([
            'Profile Image',
            <FilePreviewCell key="profileImage" fileName={visitor.profileImageFileName} previewUrl={getFilePreviewUrl?.(visitor.profileImageFileRef)} />,
          ])
          for (const field of visitorInfoCustomFields) {
            rows.push([
              visitors.length > 1 ? `Visitor ${index + 1} — ${field.label}` : field.label,
              <DynamicFieldValueCell
                key={`${field.key}-${index}`}
                field={field}
                value={visitor.customFieldValues?.[field.key]}
                getFilePreviewUrl={getFilePreviewUrl}
              />,
            ])
          }
          return rows
        })}
      />

      <GroupSummarySections
        groups={visitorInfoGroups}
        fields={visitorInfoAllFields}
        groupValues={formState.groupValues}
        flatValues={visitorGroupFlatValues}
        getFilePreviewUrl={getFilePreviewUrl}
      />

      <SummarySection
        title="Visit Info"
        rows={[
          ['Purpose', formState.visitInfo.purpose],
          ['Date', formState.visitInfo.preferredDate],
          ['Time', formState.visitInfo.preferredTime],
          ['Location', formState.visitInfo.location],
          ['Building', formState.visitInfo.building],
          ...visitDetailsCustomFields.map(
            (field): [string, ReactNode] => [
              field.label,
              <DynamicFieldValueCell
                key={field.key}
                field={field}
                value={formState.customFieldValues[field.key] as DynamicFieldValue}
                getFilePreviewUrl={getFilePreviewUrl}
              />,
            ],
          ),
        ]}
      />

      {visitDetailsStep && (
        <GroupSummarySections
          groups={visitDetailsStep.groups}
          fields={visitDetailsStep.fields}
          groupValues={formState.groupValues}
          flatValues={resolveGroupFlatValues(visitDetailsStep.groups, formState.groupValues, formState.customFieldValues)}
          getFilePreviewUrl={getFilePreviewUrl}
        />
      )}

      {carriedItemsCustomFields.length > 0 && (
        <SummarySection
          title="Carried Items"
          rows={carriedItemsCustomFields.map(
            (field): [string, ReactNode] => [
              field.label,
              <DynamicFieldValueCell
                key={field.key}
                field={field}
                value={formState.customFieldValues[field.key] as DynamicFieldValue}
                getFilePreviewUrl={getFilePreviewUrl}
              />,
            ],
          )}
        />
      )}

      <GroupSummarySections
        groups={carriedItemsGroups}
        fields={carriedItemsAllFields}
        groupValues={formState.groupValues}
        flatValues={carriedItemsGroupFlatValues}
        getFilePreviewUrl={getFilePreviewUrl}
      />

      {formState.vehicles.length > 0 &&
        vehicleCustomFields.length > 0 &&
        formState.vehicles.map((vehicle, index) => (
          <SummarySection
            key={`vehicle-${index}`}
            title={`Vehicle ${index + 1}`}
            rows={vehicleCustomFields.map((field): [string, ReactNode] => [
              field.label,
              <DynamicFieldValueCell
                key={field.key}
                field={field}
                value={(vehicle.customFieldValues as Record<string, DynamicFieldValue> | undefined)?.[field.key]}
                getFilePreviewUrl={getFilePreviewUrl}
              />,
            ])}
          />
        ))}

      <GroupSummarySections
        groups={vehicleInfoGroups}
        fields={vehicleInfoAllFields}
        groupValues={formState.groupValues}
        flatValues={vehicleGroupFlatValues}
        getFilePreviewUrl={getFilePreviewUrl}
      />

      {customSteps.map((step) => {
        const groupedFieldKeys = new Set(step.groups.flatMap((group) => group.fieldKeys))
        const ungroupedFields = step.fields.filter((field) => !groupedFieldKeys.has(field.key))
        return (
          <div key={step.key} className="flex flex-col gap-6">
            {ungroupedFields.length > 0 && (
              <SummarySection
                title={step.name || prettifyKey(step.key)}
                rows={ungroupedFields.map(
                  (field): [string, ReactNode] => [
                    field.label,
                    <DynamicFieldValueCell
                      key={field.key}
                      field={field}
                      value={formState.customFieldValues[field.key] as DynamicFieldValue}
                      getFilePreviewUrl={getFilePreviewUrl}
                    />,
                  ],
                )}
              />
            )}
            <GroupSummarySections
              groups={step.groups}
              fields={step.fields}
              groupValues={formState.groupValues}
              flatValues={resolveGroupFlatValues(step.groups, formState.groupValues, formState.customFieldValues)}
              getFilePreviewUrl={getFilePreviewUrl}
            />
          </div>
        )
      })}

      {Object.keys(formState.consent).length > 0 && (
        <SummarySection
          title="Consent"
          rows={Object.entries(formState.consent).map(([key, agreed]) => [prettifyKey(key), agreed ? 'Agreed' : 'Not agreed'])}
        />
      )}

      <div className="sticky bottom-0 -mx-4 -mb-4 flex flex-wrap gap-3 rounded-b-2xl border-t border-border-subtle bg-surface px-4 py-3 sm:-mx-6 sm:-mb-6 sm:px-6 md:static md:m-0 md:border-0 md:p-0">
        <button
          type="button"
          onClick={onBack}
          disabled={status === 'submitting'}
          title="Go back to the previous step"
          className="cursor-pointer rounded-lg border border-primary px-6 py-3 text-body font-semibold text-primary transition-colors enabled:hover:bg-primary/10 disabled:cursor-not-allowed"
        >
          ← Back
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={status === 'submitting'}
          title="Submit your visit request"
          className="flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-primary px-6 py-3 text-body font-semibold text-white transition-colors enabled:hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {status === 'submitting' && <Spinner className="size-4 border-white/40 border-t-white" />}
          {status === 'submitting' ? 'Submitting…' : 'Submit Request'}
        </button>
      </div>
    </div>
  )
}
