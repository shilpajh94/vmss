import { ChevronLeftIcon } from '../../components/icons'
import { LoadingState } from '../../components/ui/LoadingState'
import { SelectField } from '../../components/ui/SelectField'
import { TextField } from '../../components/ui/TextField'
import { ToggleSwitch } from '../../components/ui/ToggleSwitch'
import { usePageHeader } from '../../context/page-header-context'
import { useAdminFloorForm } from './hooks/use-admin-floor-form'

const CAPACITY_TYPE_OPTIONS = [
  { value: 'guests', label: 'Guests' },
  { value: 'staff', label: 'Staff' },
]

const ACCESS_LEVEL_OPTIONS = [
  { value: 'public', label: 'Public' },
  { value: 'restricted', label: 'Restricted' },
  { value: 'secure', label: 'Secure' },
]

export function AdminFloorFormPage() {
  const {
    isEditMode,
    buildings,
    isLoading,
    errorMessage,
    retry,
    values,
    errors,
    isSaving,
    updateField,
    submit,
    cancel,
  } = useAdminFloorForm()

  usePageHeader({ description: 'Manage building floors, occupancy capacity limits, and access group clearance' })

  const buildingOptions = buildings.map((building) => ({ value: building.id, label: building.name }))

  return (
    <div className="mx-auto flex w-full max-w-[1160px] flex-col gap-6">
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={cancel}
          aria-label="Back"
          className="flex size-9 items-center justify-center rounded-full border border-border bg-surface"
        >
          <ChevronLeftIcon className="size-4" />
        </button>
        <h1 className="font-display text-2xl font-bold text-text">{isEditMode ? 'Edit Floor' : 'Add Floor'}</h1>
      </div>

      {errorMessage ? (
          <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-border bg-surface p-12 text-center">
            <p className="font-body text-sm text-danger">{errorMessage}</p>
            <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
              Try again
            </button>
          </div>
        ) : isLoading ? (
          <LoadingState label="Loading…" className="py-12" />
        ) : (
          <div className="flex w-full flex-col gap-6 rounded-2xl border border-border bg-surface px-6 py-8">
            <div className="flex gap-6">
              <div className="flex-1">
                <TextField label="Floor Name" required value={values.name} onChange={(name) => updateField('name', name)} error={errors.name} />
              </div>
              <div className="flex-1">
                <SelectField
                  label="Building"
                  required
                  value={values.buildingId}
                  onChange={(buildingId) => updateField('buildingId', buildingId)}
                  options={buildingOptions}
                  placeholder="Select building..."
                  error={errors.buildingId}
                />
              </div>
            </div>
            <div className="flex gap-6">
              <div className="flex-1">
                <TextField
                  label="Floor Number"
                  type="number"
                  value={String(values.floorNumber)}
                  onChange={(value) => updateField('floorNumber', Number(value) || 0)}
                />
              </div>
              <div className="flex-1">
                <TextField
                  label="Capacity"
                  type="number"
                  value={String(values.capacity)}
                  onChange={(value) => updateField('capacity', Number(value) || 0)}
                />
              </div>
              <div className="flex-1">
                <SelectField
                  label="Unit"
                  value={values.capacityType}
                  onChange={(capacityType) => updateField('capacityType', capacityType as typeof values.capacityType)}
                  options={CAPACITY_TYPE_OPTIONS}
                />
              </div>
            </div>
            <SelectField
              label="Access Level"
              value={values.accessLevel}
              onChange={(accessLevel) => updateField('accessLevel', accessLevel as typeof values.accessLevel)}
              options={ACCESS_LEVEL_OPTIONS}
            />
            <ToggleSwitch
              label={values.isActive ? 'Active' : 'Inactive'}
              checked={values.isActive}
              onChange={(checked) => updateField('isActive', checked)}
            />

            <div className="flex items-center justify-end gap-3 border-t border-border pt-4">
              <button type="button" onClick={cancel} className="rounded-full border border-border bg-surface px-6 py-2.5 font-body text-sm font-semibold text-text">
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void submit()}
                disabled={isSaving}
                className="rounded-full bg-admin-accent px-6 py-2.5 font-body text-sm font-semibold text-white disabled:opacity-50"
              >
                {isSaving ? 'Saving…' : isEditMode ? 'Save Changes' : 'Save Floor'}
              </button>
            </div>
          </div>
        )}
    </div>
  )
}
