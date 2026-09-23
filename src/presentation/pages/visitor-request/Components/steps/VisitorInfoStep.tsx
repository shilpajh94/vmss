import { FieldGroupsSection } from '../../../../components/dynamic-fields/FieldGroupsSection'
import { resolveGroupFlatValues } from '../../../../components/dynamic-fields/field-group-visibility'
import type { GroupInstance } from '../../../../components/dynamic-fields/RepeatableFieldGroup'
import { SegmentedToggle } from '../../../../components/ui/SegmentedToggle'
import type { EffectiveFormFieldGroup, FormField } from '../../../../../domain/entities/form-builder-schema'
import type { VisitorInfoFieldState } from '../../hooks/use-visitor-request-wizard'
import { type RegistrationType, type VisitorCategoriesFieldState, type VisitorFormEntry } from '../../types'
import { VisitorFieldsForm } from './VisitorFieldsForm'

interface VisitorInfoStepProps {
  registrationType: RegistrationType
  onRegistrationTypeChange: (type: RegistrationType) => void
  primaryContact: VisitorFormEntry
  onPrimaryContactChange: (entry: VisitorFormEntry) => void
  uploadFile: (file: File) => Promise<string>
  getFilePreviewUrl?: (fileRef?: string) => string | undefined
  errors: Record<string, string>
  visitorCategoriesState: VisitorCategoriesFieldState
  onRetryVisitorCategories: () => void
  /** Branch-configured (form-builder) active/required state for ID proof
   * and profile photo — see `use-visitor-request-wizard.ts`.
   */
  visitorInfoFields: VisitorInfoFieldState
  /** Admin-authored (non-system) Visitor Info fields, passed straight
   * through to each visitor's own `VisitorFieldsForm`
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
  visitorCategoriesState,
  onRetryVisitorCategories,
  visitorInfoFields,
  customFields,
  groups,
  groupFields,
  groupValues,
  onGroupValuesChange,
}: VisitorInfoStepProps) {
  // A group's condition can watch the built-in Registration Type toggle
  // (system field key `registration_type` — see `field-type-catalog.ts`),
  // which isn't part of `primaryContact.customFieldValues` since it renders
  // through its own `SegmentedToggle` rather than `DynamicField`, or any
  // other same-step field the primary contact has answered.
  const groupFlatValues = resolveGroupFlatValues(groups, groupValues, {
    registration_type: registrationType,
    ...primaryContact.customFieldValues,
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <span className="text-body font-medium text-text">Registration Type</span>
        <div className="w-[320px]">
          <SegmentedToggle
            options={[
              { value: 'individual', label: 'Individual' },
              { value: 'group', label: 'Group' },
            ]}
            value={registrationType}
            onChange={(value) => onRegistrationTypeChange(value as RegistrationType)}
            variant="pill"
          />
        </div>
      </div>

      <div className="flex flex-col gap-3">
        {registrationType === 'group' && <h3 className="text-h3 text-text">Primary Contact Details</h3>}
        <VisitorFieldsForm
          value={primaryContact}
          onChange={onPrimaryContactChange}
          showContactMethod
          uploadFile={uploadFile}
          getFilePreviewUrl={getFilePreviewUrl}
          errors={errors}
          visitorCategoriesState={visitorCategoriesState}
          onRetryVisitorCategories={onRetryVisitorCategories}
          visitorInfoFields={visitorInfoFields}
          customFields={customFields}
        />
      </div>

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
