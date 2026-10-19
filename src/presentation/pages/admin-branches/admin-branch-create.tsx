import { BackButton } from '../../components/BackButton'
import { SelectField } from '../../components/ui/SelectField'
import { PendingButton } from '../../components/ui/PendingButton'
import { TextField } from '../../components/ui/TextField'
import { TextareaField } from '../../components/ui/TextareaField'
import { SwitchField } from '../../components/ui/ToggleSwitch'
import { usePageHeader } from '../../context/page-header-context'
import { COUNTRY_OPTIONS, OPERATING_HOURS_OPTIONS } from './branch-form-options'
import { useAdminBranchCreate } from './hooks/use-admin-branch-create'

const BREADCRUMB = [{ label: 'Organisation Admin' }, { label: 'Branches' }, { label: 'Create New Branch', isActive: true }]

export function AdminBranchCreatePage() {
  const { employees, values, errors, isSaving, updateField, submit, cancel } = useAdminBranchCreate()
  const employeeOptions = employees.map((employee) => ({ value: employee.id, label: employee.fullName }))

  usePageHeader({ breadcrumb: BREADCRUMB })

  return (
    <>
      <div className="flex items-center gap-4">
        <BackButton onClick={cancel} />
        <div className="flex flex-col gap-1">
          <h1 className="font-display text-xl font-bold md:text-2xl text-text">Create New Branch</h1>
          <p className="font-body text-[13px] text-text-muted">
            Provision a new logical branch office with physical addresses, operating parameters, and contact references.
          </p>
        </div>
      </div>

      <div className="flex w-full flex-col gap-6 rounded-2xl border border-border bg-surface p-4 md:p-6">
        <div className="flex flex-col gap-4">
          <h2 className="font-display text-base font-semibold text-text">Branch Identity &amp; Geography</h2>
          <div className="flex flex-col gap-4 md:flex-row md:gap-6">
            <div className="flex-1">
              <TextField label="Branch Name" required value={values.name} onChange={(name) => updateField('name', name)} error={errors.name} />
            </div>
            <div className="flex-1">
              <TextField
                label="Branch Code"
                required
                value={values.code}
                onChange={(code) => updateField('code', code)}
                error={errors.code}
              />
            </div>
          </div>
          <div className="flex flex-col gap-4 md:flex-row md:gap-6">
            <div className="flex-1">
              <TextField
                label="Location / City"
                required
                value={values.city}
                onChange={(city) => updateField('city', city)}
                error={errors.city}
              />
            </div>
            <div className="flex-1">
              <SelectField
                label="Country"
                required
                value={values.country}
                onChange={(country) => updateField('country', country)}
                options={COUNTRY_OPTIONS}
                error={errors.country}
              />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <TextareaField
              label="Physical Address"
              value={values.address}
              onChange={(address) => updateField('address', address)}
              placeholder="Enter complete postal street address, landmarks, and area code..."
              rows={2}
            />
            {errors.address && <p className="text-caption text-danger">{errors.address}</p>}
          </div>
        </div>

        <div className="h-px w-full bg-border" />

        <div className="flex flex-col gap-4">
          <h2 className="font-display text-base font-semibold text-text">Operations &amp; Administration</h2>
          <div className="flex flex-col gap-4 md:flex-row md:gap-6">
            <div className="flex-1">
              <SelectField
                label="Contact Person (Regional Admin)"
                required
                value={values.contactPersonUserId}
                onChange={(contactPersonUserId) => updateField('contactPersonUserId', contactPersonUserId)}
                options={employeeOptions}
                placeholder="Select employee..."
                error={errors.contactPersonUserId}
              />
            </div>
            <div className="flex-1">
              <TextField
                label="Contact Email Address"
                type="email"
                required
                value={values.contactEmail}
                onChange={(contactEmail) => updateField('contactEmail', contactEmail)}
                error={errors.contactEmail}
              />
            </div>
          </div>
          <div className="flex flex-col gap-4 md:flex-row md:gap-6">
            <div className="flex-1">
              <TextField
                label="Contact Phone"
                required
                value={values.contactPhone}
                onChange={(contactPhone) => updateField('contactPhone', contactPhone)}
                error={errors.contactPhone}
              />
            </div>
            <div className="flex flex-1 gap-3">
              <div className="flex-1">
                <SelectField
                  label="Operating Hours (From)"
                  value={values.operatingHoursFrom ?? ''}
                  onChange={(operatingHoursFrom) => updateField('operatingHoursFrom', operatingHoursFrom)}
                  options={OPERATING_HOURS_OPTIONS}
                />
              </div>
              <div className="flex-1">
                <SelectField
                  label="Operating Hours (To)"
                  value={values.operatingHoursTo ?? ''}
                  onChange={(operatingHoursTo) => updateField('operatingHoursTo', operatingHoursTo)}
                  options={OPERATING_HOURS_OPTIONS}
                />
              </div>
            </div>
          </div>
          <div className="flex flex-col gap-4 md:flex-row md:gap-6">
            <div className="w-full md:w-[240px] md:shrink-0">
              <SwitchField
                label="Operational Status"
                checked={values.isActive}
                onChange={(checked) => updateField('isActive', checked)}
                stateLabel={values.isActive ? 'Active / Open' : 'Inactive / Closed'}
              />
            </div>
            <div className="flex-1">
              <TextareaField
                label="Internal Administration Notes / Directives"
                value={values.notes ?? ''}
                onChange={(notes) => updateField('notes', notes)}
                placeholder="Specify any branch level specific watchlist configurations, guest-escort overrides, or safety rules..."
                rows={2}
              />
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-3 border-t border-border pt-4">
          <button type="button" onClick={cancel} className="rounded-lg px-5 py-2.5 font-body text-sm font-semibold text-text-muted">
            Cancel
          </button>
          <PendingButton
            onClick={() => void submit()}
            pending={isSaving}
            pendingLabel="Creating…"
            className="rounded-full bg-admin-accent px-6 py-2.5 font-body text-sm font-semibold text-white disabled:opacity-50"
          >
            Create Branch
          </PendingButton>
        </div>
      </div>
    </>
  )
}
