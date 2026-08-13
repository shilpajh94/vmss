import { SelectField } from '../../../../components/ui/SelectField'
import { TextField } from '../../../../components/ui/TextField'
import { TextareaField } from '../../../../components/ui/TextareaField'
import type { VisitInfoFormState } from '../../types'

const PURPOSE_OPTIONS = [
  { value: 'business-meeting', label: 'Business Meeting' },
  { value: 'interview', label: 'Interview' },
  { value: 'delivery', label: 'Delivery' },
  { value: 'personal-visit', label: 'Personal Visit' },
  { value: 'vendor-contractor', label: 'Vendor / Contractor' },
  { value: 'other', label: 'Other' },
]

const DURATION_OPTIONS = [
  { value: '30-minutes', label: '30 minutes' },
  { value: '1-hour', label: '1 hour' },
  { value: '2-hours', label: '2 hours' },
  { value: 'half-day', label: 'Half day' },
  { value: 'full-day', label: 'Full day' },
  { value: 'multi-day', label: 'Multi-day' },
]

interface VisitInfoStepProps {
  value: VisitInfoFormState
  onChange: (value: VisitInfoFormState) => void
  errors: Record<string, string>
}

export function VisitInfoStep({ value, onChange, errors }: VisitInfoStepProps) {
  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-h3 text-text">Visit Details</h3>
      <div className="grid grid-cols-2 gap-4">
        <SelectField
          label="Purpose of Visit"
          placeholder="Select purpose"
          options={PURPOSE_OPTIONS}
          value={value.purpose}
          onChange={(purpose) => onChange({ ...value, purpose })}
          error={errors.purpose}
          required
        />
        <TextField
          label="Host Name or Email"
          placeholder="Enter host name or email"
          value={value.hostNameOrEmail}
          onChange={(hostNameOrEmail) => onChange({ ...value, hostNameOrEmail })}
          error={errors.hostNameOrEmail}
          required
        />
        <TextField
          label="Preferred Visit Date"
          type="date"
          value={value.preferredDate}
          onChange={(preferredDate) => onChange({ ...value, preferredDate })}
          error={errors.preferredDate}
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
        <TextField
          label="Location"
          placeholder="Enter site/location"
          value={value.location}
          onChange={(location) => onChange({ ...value, location })}
          error={errors.location}
          required
        />
        <TextField
          label="Building"
          placeholder="Enter building"
          value={value.building}
          onChange={(building) => onChange({ ...value, building })}
          error={errors.building}
          required
        />
        <TextField
          label="Department to Visit"
          placeholder="Enter department name"
          value={value.department}
          onChange={(department) => onChange({ ...value, department })}
          error={errors.department}
          required
        />
      </div>
      <TextareaField
        label="Additional Notes / Special Requirements"
        placeholder="Any special requirements, accessibility needs, or notes for the host…"
        value={value.notes}
        onChange={(notes) => onChange({ ...value, notes })}
      />
    </div>
  )
}
