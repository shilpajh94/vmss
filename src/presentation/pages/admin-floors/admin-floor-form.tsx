import { ChevronLeftIcon } from '../../components/icons'
import { FormSkeleton } from '../../components/ui/Skeleton'
import { PendingButton } from '../../components/ui/PendingButton'
import { SelectField } from '../../components/ui/SelectField'
import { TextField } from '../../components/ui/TextField'
import { ToggleSwitch } from '../../components/ui/ToggleSwitch'
import { WholeNumberField } from '../../components/ui/WholeNumberField'
import { FLOOR_LIMITS } from './floor-form-validation'
import { usePageHeader } from '../../context/page-header-context'
import { useAdminFloorForm } from './hooks/use-admin-floor-form'
import { ErrorState } from '../../components/ui/ErrorState'

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
        <h1 className="font-display text-xl font-bold md:text-2xl text-text">{isEditMode ? 'Edit Floor' : 'Add Floor'}</h1>
      </div>

      {errorMessage ? (
          <ErrorState message={errorMessage} onRetry={retry} />
        ) : isLoading ? (
          <FormSkeleton rows={3} columns={2} label="Loading floor…" />
        ) : (
          <div className="flex w-full flex-col gap-6 rounded-2xl border border-border bg-surface px-6 py-8">
            <div className="flex flex-col gap-4 md:flex-row md:gap-6">
              <div className="flex-1">
                <TextField
                  label="Floor Name"
                  required
                  value={values.name}
                  onChange={(name) => updateField('name', name)}
                  error={errors.name}
                  maxLength={FLOOR_LIMITS.name}
                />
              </div>
              <div className="flex-1">
                <SelectField
                  label="Building"
                  required
                  value={values.buildingId}
                  onChange={(buildingId) => updateField('buildingId', buildingId)}
                  options={buildingOptions}
                  disabled={isEditMode}
                  placeholder="Select building..."
                  error={errors.buildingId}
                />
              </div>
            </div>
            <div className="flex flex-col gap-4 md:flex-row md:gap-6">
              <div className="flex-1">
                <WholeNumberField
                  label="Floor Number"
                  required
                  allowNegative
                  value={values.floorNumber}
                  onChange={(floorNumber) => updateField('floorNumber', floorNumber)}
                  error={errors.floorNumber}
                  helperText="0 is the ground floor; basements are negative."
                />
              </div>
              <div className="flex-1">
                <WholeNumberField
                  label="Capacity"
                  value={values.capacity}
                  onChange={(capacity) => updateField('capacity', capacity)}
                  error={errors.capacity}
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

            <div className="flex flex-wrap items-center justify-end gap-3 border-t border-border pt-4">
              <button type="button" onClick={cancel} className="rounded-full border border-border bg-surface px-6 py-2.5 font-body text-sm font-semibold text-text">
                Cancel
              </button>
              <PendingButton
                onClick={() => void submit()}
                pending={isSaving}
                pendingLabel="Saving…"
                className="rounded-full bg-admin-accent px-6 py-2.5 font-body text-sm font-semibold text-on-accent disabled:opacity-50"
              >
                {isEditMode ? 'Save Changes' : 'Save Floor'}
              </PendingButton>
            </div>
          </div>
        )}
    </div>
  )
}
