import { FieldGroupsSection } from '../../../components/dynamic-fields/FieldGroupsSection'
import { resolveGroupFlatValues } from '../../../components/dynamic-fields/field-group-visibility'
import type { GroupInstance } from '../../../components/dynamic-fields/RepeatableFieldGroup'
import type { VisitorInfoFieldState } from '../../visitor-request/hooks/use-visitor-request-wizard'
import type { RegistrationType } from '../../visitor-request/types'
import type { EffectiveFormFieldGroup, FormField } from '../../../../domain/entities/form-builder-schema'
import type { VisitorCategory } from '../../../../domain/entities/visitor-category-schema'
import type { StaffVisitorFormEntry } from '../types'
import { PrimaryContactCard } from './PrimaryContactCard'
import { RegistrationTypeToggle } from './RegistrationTypeToggle'

interface VisitorInfoStepProps {
  registrationType: RegistrationType
  onRegistrationTypeChange: (type: RegistrationType) => void
  primaryContact: StaffVisitorFormEntry
  onPrimaryContactChange: (entry: StaffVisitorFormEntry) => void
  uploadFile: (file: File) => Promise<string>
  getFilePreviewUrl?: (fileRef?: string) => string | undefined
  errors: Record<string, string>
  visitorCategories?: VisitorCategory[]
  /** Branch-configured (form-builder) active/required state for ID proof
   * and profile photo — see `use-visitor-request-wizard.ts`.
   */
  visitorInfoFields: VisitorInfoFieldState
  /** Admin-authored (non-system) Visitor Info fields
   * (add-generic-custom-field-support). */
  customFields: FormField[]
  /** Visitor Info's own admin-defined field groups
   * (add-repeatable-field-groups / add-conditional-field-groups), rendered
   * once for the whole step (not per-visitor) via `FieldGroupsSection` —
   * e.g. an admin-created "Additional Visitors" group is now the supported
   * way to collect more than one visitor, replacing the old built-in
   * "Visitor Details"/"+ Add Visitor" UI (removed — the backend won't allow
   * the seeded "visitors" system group to be made non-repeatable, so it
   * couldn't be branch-configured off; see `GroupCard.tsx`). */
  groups: EffectiveFormFieldGroup[]
  /** Every non-system Visitor Info field, including grouped ones — used to
   * resolve `groups`' `fieldKeys` (`customFields` above excludes them). */
  groupFields: FormField[]
  groupValues: Record<string, GroupInstance[]>
  onGroupValuesChange: (groupValues: Record<string, GroupInstance[]>) => void
}

export function VisitorInfoStep({
  registrationType,
  onRegistrationTypeChange,
  primaryContact,
  onPrimaryContactChange,
  uploadFile,
  getFilePreviewUrl,
  errors,
  visitorCategories,
  visitorInfoFields,
  customFields,
  groups,
  groupFields,
  groupValues,
  onGroupValuesChange,
}: VisitorInfoStepProps) {
  // See visitor-request/Components/steps/VisitorInfoStep.tsx's matching
  // comment — `registration_type` is the built-in Registration Type
  // toggle's system field key.
  const groupFlatValues = resolveGroupFlatValues(groups, groupValues, {
    registration_type: registrationType,
    ...primaryContact.customFieldValues,
  })

  return (
    <div className="flex flex-col gap-6">
      <RegistrationTypeToggle value={registrationType} onChange={onRegistrationTypeChange} />

      <PrimaryContactCard
        value={primaryContact}
        onChange={onPrimaryContactChange}
        uploadFile={uploadFile}
        getFilePreviewUrl={getFilePreviewUrl}
        errors={errors}
        visitorCategories={visitorCategories}
        visitorInfoFields={visitorInfoFields}
        customFields={customFields}
      />

      <FieldGroupsSection
        groups={groups}
        fields={groupFields}
        flatValues={groupFlatValues}
        groupValues={groupValues}
        onGroupValuesChange={onGroupValuesChange}
      />
    </div>
  )
}
