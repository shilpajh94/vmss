import { CustomFieldsSection } from '../../../../components/dynamic-fields/CustomFieldsSection'
import type { DynamicFieldValue } from '../../../../components/dynamic-fields/DynamicField'
import { SelectField } from '../../../../components/ui/SelectField'
import { TextField } from '../../../../components/ui/TextField'
import { TextareaField } from '../../../../components/ui/TextareaField'
import type { Branch } from '../../../../../domain/entities/branch-schema'
import type { Building } from '../../../../../domain/entities/building-schema'
import type { FormField } from '../../../../../domain/entities/form-builder-schema'
import type { VisitInfoFormState } from '../../types'
import { todayAsDateInputValue } from '../../../../utils/local-date-input-value'
import { EXPECTED_DURATION_OPTIONS as DURATION_OPTIONS } from '../../../../utils/expected-duration-options'
import { PURPOSE_OF_VISIT_OPTIONS as PURPOSE_OPTIONS } from '../../../../utils/purpose-of-visit-options'

interface VisitInfoStepProps {
  value: VisitInfoFormState
  onChange: (value: VisitInfoFormState) => void
  errors: Record<string, string>
  branches?: Branch[]
  buildings?: Building[]
  /** Branch-configured (form-builder) active state for the toggleable
   * "Additional Notes" field. `expected_duration` is intentionally not
   * gated here — it's structurally required by the backend regardless of
   * form-builder configuration (see design.md Decision 3 / Risks).
   */
  additionalNotesActive: boolean
  /** Branch-configured (form-builder) Purpose of Visit choices — the
   * field's own `options`, not a fixed set
   * (make-id-proof-and-vehicle-type-configurable). Empty when unset, in
   * which case this step falls back to its hardcoded default list. */
  purposeOfVisitOptions: string[]
  /** Admin-authored (non-system) Visit Details fields
   * (add-generic-custom-field-support). */
  customFields: FormField[]
  customFieldValues: Record<string, DynamicFieldValue>
  onCustomFieldValuesChange: (value: Record<string, DynamicFieldValue>) => void
}

// Neither host nor department is collected here anymore
// (role-based-invitation-workflow): every invitation starts owned by the
// receiving organisation's front-office role by default, and reception
// fills in the department afterward — via the Edit Invitation modal — once
// they know the visitor's actual requirements. Both fields rarely have a
// correct answer at this point in the flow for a visitor or for staff
// booking on a visitor's behalf.
export function VisitInfoStep({
  value,
  onChange,
  errors,
  branches,
  buildings,
  additionalNotesActive,
  purposeOfVisitOptions,
  customFields,
  customFieldValues,
  onCustomFieldValuesChange,
}: VisitInfoStepProps) {
  const purposeOptions =
    purposeOfVisitOptions.length > 0 ? purposeOfVisitOptions.map((option) => ({ value: option, label: option })) : PURPOSE_OPTIONS
  const selectedBranch = branches?.find((branch) => branch.name === value.location)
  const buildingOptions = (selectedBranch ? buildings?.filter((building) => building.branchId === selectedBranch.id) : buildings)?.map(
    (building) => ({ value: building.name, label: building.name }),
  )

  const handleLocationChange = (location: string) => {
    onChange({ ...value, location, building: '' })
  }

  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-h3 text-text">Visit Details</h3>
      <div className="grid grid-cols-2 gap-4">
        <SelectField
          label="Purpose of Visit"
          placeholder="Select purpose"
          options={purposeOptions}
          value={value.purpose}
          onChange={(purpose) => onChange({ ...value, purpose })}
          error={errors.purpose}
          required
        />
        <TextField
          label="Preferred Visit Date"
          type="date"
          value={value.preferredDate}
          onChange={(preferredDate) => onChange({ ...value, preferredDate })}
          error={errors.preferredDate}
          min={todayAsDateInputValue()}
          required
        />
        <TextField
          label="Preferred Visit Time"
          type="time"
          value={value.preferredTime}
          onChange={(preferredTime) => onChange({ ...value, preferredTime })}
          error={errors.preferredTime}
          required
        />
        <SelectField
          label="Expected Duration"
          placeholder="Select duration"
          options={DURATION_OPTIONS}
          value={value.expectedDuration}
          onChange={(expectedDuration) => onChange({ ...value, expectedDuration })}
          error={errors.expectedDuration}
          required
        />
        {branches ? (
          <SelectField
            label="Location"
            placeholder="Select location"
            options={branches.map((branch) => ({ value: branch.name, label: branch.name }))}
            value={value.location}
            onChange={handleLocationChange}
            error={errors.location}
            required
          />
        ) : (
          <TextField
            label="Location"
            placeholder="Enter site/location"
            value={value.location}
            onChange={(location) => onChange({ ...value, location })}
            error={errors.location}
            required
          />
        )}
        {buildingOptions ? (
          <SelectField
            label="Building"
            placeholder="Select building"
            options={buildingOptions}
            value={value.building}
            onChange={(building) => onChange({ ...value, building })}
            error={errors.building}
            required
          />
        ) : (
          <TextField
            label="Building"
            placeholder="Enter building"
            value={value.building}
            onChange={(building) => onChange({ ...value, building })}
            error={errors.building}
            required
          />
        )}
      </div>
      {additionalNotesActive && (
        <TextareaField
          label="Additional Notes / Special Requirements"
          placeholder="Any special requirements, accessibility needs, or notes for the host…"
          value={value.notes}
          onChange={(notes) => onChange({ ...value, notes })}
        />
      )}
      <CustomFieldsSection fields={customFields} value={customFieldValues} onChange={onCustomFieldValuesChange} />
    </div>
  )
}
