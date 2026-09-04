import { AutocompleteField } from '../../../../components/ui/AutocompleteField'
import { SelectField } from '../../../../components/ui/SelectField'
import { TextField } from '../../../../components/ui/TextField'
import { TextareaField } from '../../../../components/ui/TextareaField'
import type { Branch } from '../../../../../domain/entities/branch-schema'
import type { Building } from '../../../../../domain/entities/building-schema'
import type { Department } from '../../../../../domain/entities/department-schema'
import type { HostSearchResult } from '../../../../../domain/entities/host-search-schema'
import type { VisitInfoFormState } from '../../types'
import { todayAsDateInputValue } from '../../../../utils/local-date-input-value'
import { PURPOSE_OF_VISIT_OPTIONS as PURPOSE_OPTIONS } from '../../../../utils/purpose-of-visit-options'

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
  onSearchHosts: (query: string) => Promise<HostSearchResult[]>
  branches?: Branch[]
  buildings?: Building[]
  departments?: Department[]
}

export function VisitInfoStep({ value, onChange, errors, onSearchHosts, branches, buildings, departments }: VisitInfoStepProps) {
  const handleHostSearch = async (query: string) => {
    const results = await onSearchHosts(query)
    return results.map((host) => ({
      value: host.email,
      label: host.department ? `${host.name} (${host.email}) — ${host.department}` : `${host.name} (${host.email})`,
      id: host.id,
    }))
  }

  const selectedBranch = branches?.find((branch) => branch.name === value.location)
  const buildingOptions = (selectedBranch ? buildings?.filter((building) => building.branchId === selectedBranch.id) : buildings)?.map(
    (building) => ({ value: building.name, label: building.name }),
  )
  const departmentOptions = (
    selectedBranch ? departments?.filter((department) => department.branchId === selectedBranch.id) : departments
  )?.map((department) => ({ value: department.name, label: department.name }))

  const handleLocationChange = (location: string) => {
    onChange({ ...value, location, building: '', department: '' })
  }

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
        <AutocompleteField
          label="Host Name or Email"
          placeholder="Search by host name or email"
          value={value.hostNameOrEmail}
          onChange={(hostNameOrEmail) => onChange({ ...value, hostNameOrEmail, hostId: '' })}
          onSelect={(option) => onChange({ ...value, hostNameOrEmail: option.value, hostId: option.id ?? '' })}
          onSearch={handleHostSearch}
          error={errors.hostNameOrEmail}
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
        {departmentOptions ? (
          <SelectField
            label="Department to Visit"
            placeholder="Select department"
            options={departmentOptions}
            value={value.department}
            onChange={(department) => onChange({ ...value, department })}
            error={errors.department}
            required
          />
        ) : (
          <TextField
            label="Department to Visit"
            placeholder="Enter department name"
            value={value.department}
            onChange={(department) => onChange({ ...value, department })}
            error={errors.department}
            required
          />
        )}
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
