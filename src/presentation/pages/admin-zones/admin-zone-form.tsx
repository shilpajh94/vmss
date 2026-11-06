import { FormPageHeader } from '../../components/FormPageHeader'
import { Checkbox } from '../../components/ui/Checkbox'
import { ErrorState } from '../../components/ui/ErrorState'
import { PendingButton } from '../../components/ui/PendingButton'
import { SelectField } from '../../components/ui/SelectField'
import { FormSkeleton } from '../../components/ui/Skeleton'
import { TextField } from '../../components/ui/TextField'
import { ToggleSwitch } from '../../components/ui/ToggleSwitch'
import { usePageHeader } from '../../context/page-header-context'
import { useAdminZoneForm } from './hooks/use-admin-zone-form'

export function AdminZoneFormPage() {
  const form = useAdminZoneForm()
  const { details, errors, isEditMode } = form

  usePageHeader({ description: 'Define the zones visitors can be granted access to and the gates that lead into them' })

  const branchOptions = form.references.branches.map((branch) => ({ value: branch.id, label: branch.name }))
  const fieldLabelClassName = 'text-[13px] font-semibold text-text-secondary'

  return (
    <div className="mx-auto flex w-full max-w-[1160px] flex-col gap-6">
      <FormPageHeader title={isEditMode ? 'Edit Zone' : 'Add Zone'} onBack={form.cancel} />

      {form.errorMessage ? (
        <ErrorState message={form.errorMessage} onRetry={form.retry} />
      ) : form.isLoading ? (
        <FormSkeleton rows={3} columns={2} label="Loading zone…" />
      ) : (
        <div className="flex w-full flex-col gap-7 rounded-2xl border border-border bg-surface px-6 py-8">
          <div className="flex flex-col gap-4">
            <p className="font-body text-sm font-semibold text-text-muted">Zone Details</p>
            <div className="flex flex-col gap-4 md:flex-row md:gap-6">
              <div className="flex-1">
                <TextField
                  label="Zone Name"
                  required
                  value={details.name}
                  onChange={(name) => form.updateField('name', name)}
                  error={errors.name}
                  maxLength={255}
                  labelClassName={fieldLabelClassName}
                />
              </div>
              <div className="flex-1">
                <TextField
                  label="Zone Code"
                  required
                  value={details.code}
                  onChange={(code) => form.updateField('code', code)}
                  error={errors.code}
                  maxLength={50}
                  labelClassName={fieldLabelClassName}
                />
              </div>
            </div>
            <div className="flex flex-col gap-4 md:flex-row md:gap-6">
              <div className="flex-1">
                <SelectField
                  label="Branch"
                  required
                  value={details.branchId}
                  onChange={form.changeBranch}
                  options={branchOptions}
                  disabled={isEditMode}
                  placeholder="Select branch..."
                  error={errors.branchId}
                  labelClassName={fieldLabelClassName}
                />
              </div>
              <div className="flex-1">
                <SelectField
                  label="Building"
                  value={details.buildingId ?? ''}
                  onChange={form.changeBuilding}
                  options={form.buildingOptions}
                  disabled={!details.branchId}
                  placeholder={details.branchId ? 'None' : 'Select a branch first'}
                  placeholderSelectable
                  labelClassName={fieldLabelClassName}
                />
              </div>
              <div className="flex-1">
                <SelectField
                  label="Floor"
                  value={details.floorId ?? ''}
                  onChange={(floorId) => form.updateField('floorId', floorId || null)}
                  options={form.floorOptions}
                  disabled={!details.buildingId}
                  placeholder={details.buildingId ? 'None' : 'Select a building first'}
                  placeholderSelectable
                  labelClassName={fieldLabelClassName}
                />
              </div>
            </div>
          </div>

          <div className="h-px w-full bg-border" />

          <div className="flex flex-col gap-3">
            <p className="font-body text-sm font-semibold text-text-muted">Gates into this zone</p>
            {form.gateOptions.length === 0 ? (
              <p className="font-body text-sm text-text-faint">
                {details.branchId ? 'No security gates are registered for this selection.' : 'Select a branch to choose gates.'}
              </p>
            ) : (
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {form.gateOptions.map((gate) => (
                  <Checkbox key={gate.value} checked={details.gateIds.includes(gate.value)} onChange={(checked) => form.toggleGate(gate.value, checked)}>
                    {gate.label}
                  </Checkbox>
                ))}
              </div>
            )}
          </div>

          <div className="flex flex-col items-start gap-3 py-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-col gap-1">
              <p className="font-body text-sm font-semibold text-text-muted">Default zone</p>
              <p className="max-w-xl font-body text-xs text-text-faint">
                Always allowed for every visitor at this branch. Only one per branch: turning it on moves it from the current default. It still needs a linked gate.
              </p>
            </div>
            <ToggleSwitch
              label={details.isDefault ? 'Default' : 'Not default'}
              checked={details.isDefault ?? false}
              disabled={details.isActive === false}
              onChange={(checked) => form.updateField('isDefault', checked)}
            />
          </div>

          {isEditMode && (
            <div className="flex flex-col items-start gap-3 py-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-col gap-1">
                <p className="font-body text-sm font-semibold text-text-muted">Zone Status</p>
                <p className="font-body text-xs text-text-faint">An inactive zone denies every entry scan</p>
              </div>
              <ToggleSwitch
                label={details.isActive ? 'Active' : 'Inactive'}
                checked={details.isActive ?? true}
                onChange={(checked) => form.updateField('isActive', checked)}
              />
            </div>
          )}

          <div className="flex flex-wrap items-center justify-end gap-3 border-t border-border pt-4">
            <button type="button" onClick={form.cancel} className="rounded-full border border-border bg-surface px-6 py-2.5 font-body text-sm font-semibold text-text">
              Cancel
            </button>
            <PendingButton
              onClick={() => void form.submit()}
              pending={form.isSaving}
              pendingLabel="Saving…"
              className="rounded-full bg-admin-accent px-6 py-2.5 font-body text-sm font-semibold text-on-accent disabled:opacity-50"
            >
              {isEditMode ? 'Save Changes' : 'Save Zone'}
            </PendingButton>
          </div>
        </div>
      )}
    </div>
  )
}
