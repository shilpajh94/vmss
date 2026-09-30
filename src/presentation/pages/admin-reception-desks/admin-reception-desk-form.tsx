import { ChevronLeftIcon } from '../../components/icons'
import { LoadingState } from '../../components/ui/LoadingState'
import { SelectField } from '../../components/ui/SelectField'
import { TextField } from '../../components/ui/TextField'
import { usePageHeader } from '../../context/page-header-context'
import { useAdminReceptionDeskForm } from './hooks/use-admin-reception-desk-form'

const STATUS_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'maintenance', label: 'Maintenance' },
  { value: 'inactive', label: 'Inactive' },
]

export function AdminReceptionDeskFormPage() {
  const {
    isEditMode,
    buildings,
    floors,
    hostEmployees,
    isLoading,
    errorMessage,
    retry,
    values,
    errors,
    isSaving,
    updateField,
    submit,
    cancel,
  } = useAdminReceptionDeskForm()

  const buildingOptions = buildings.map((building) => ({ value: building.id, label: building.name }))
  const floorOptions = floors.map((floor) => ({ value: floor.id, label: floor.name }))
  const receptionistOptions = [
    { value: '', label: 'Unassigned' },
    ...hostEmployees.map((employee) => ({ value: employee.id, label: employee.fullName })),
  ]
  const fieldLabelClassName = 'text-[13px] font-bold uppercase text-[#475569]'

  usePageHeader({ description: 'Manage on-site registration desks, kiosks, and building entrance welcoming nodes' })

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
        <div className="flex flex-col gap-0.5">
          <h1 className="font-display text-xl font-bold md:text-2xl text-text">{isEditMode ? 'Edit Reception Desk' : 'Add Reception Desk'}</h1>
          <p className="font-body text-sm text-text-muted">
            {isEditMode ? "Update this desk's registration details" : 'Register a new on-site reception desk, kiosk, or welcoming node'}
          </p>
        </div>
      </div>

      {errorMessage ? (
        <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-border bg-surface p-4 md:p-6 text-center md:p-12">
          <p className="font-body text-sm text-danger">{errorMessage}</p>
          <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
            Try again
          </button>
        </div>
      ) : isLoading ? (
        <LoadingState label="Loading…" className="py-12" />
      ) : (
        <div className="flex w-full flex-col gap-8 rounded-2xl border border-border bg-surface p-10">
          <div className="flex flex-col gap-6">
            <div className="flex flex-col gap-4 md:flex-row md:gap-6">
              <div className="flex-1">
                <TextField
                  label="Desk Name"
                  required
                  value={values.name}
                  onChange={(name) => updateField('name', name)}
                  error={errors.name}
                  labelClassName={fieldLabelClassName}
                />
              </div>
              <div className="flex-1">
                <TextField
                  label="Desk Code"
                  required
                  value={values.code}
                  onChange={(code) => updateField('code', code)}
                  error={errors.code}
                  labelClassName={fieldLabelClassName}
                />
              </div>
            </div>
            <div className="flex flex-col gap-4 md:flex-row md:gap-6">
              <div className="flex-1">
                <SelectField
                  label="Building"
                  required
                  value={values.buildingId}
                  onChange={(buildingId) => updateField('buildingId', buildingId)}
                  options={buildingOptions}
                  placeholder="Select building..."
                  error={errors.buildingId}
                  disabled={isEditMode}
                  labelClassName={fieldLabelClassName}
                />
              </div>
              <div className="flex-1">
                <SelectField
                  label="Floor"
                  required
                  value={values.floorId}
                  onChange={(floorId) => updateField('floorId', floorId)}
                  options={floorOptions}
                  placeholder="Select floor..."
                  error={errors.floorId}
                  disabled={isEditMode}
                  labelClassName={fieldLabelClassName}
                />
              </div>
            </div>
            <div className="flex flex-col gap-4 md:flex-row md:gap-6">
              <div className="flex-1">
                <SelectField
                  label="Assigned Receptionist"
                  value={values.receptionistUserId ?? ''}
                  onChange={(receptionistUserId) => updateField('receptionistUserId', receptionistUserId || undefined)}
                  options={receptionistOptions}
                  placeholder="Select receptionist..."
                  labelClassName={fieldLabelClassName}
                />
              </div>
            </div>
            <div className="flex flex-col gap-4 md:flex-row md:gap-6">
              <div className="flex-1">
                <TextField
                  label="Operating Hours From"
                  value={values.operatingHoursFrom ?? ''}
                  onChange={(operatingHoursFrom) => updateField('operatingHoursFrom', operatingHoursFrom || undefined)}
                  placeholder="e.g. 08:00 AM"
                  labelClassName={fieldLabelClassName}
                />
              </div>
              <div className="flex-1">
                <TextField
                  label="Operating Hours To"
                  value={values.operatingHoursTo ?? ''}
                  onChange={(operatingHoursTo) => updateField('operatingHoursTo', operatingHoursTo || undefined)}
                  placeholder="e.g. 06:00 PM"
                  labelClassName={fieldLabelClassName}
                />
              </div>
            </div>
            <SelectField
              label="Status"
              required
              value={values.status}
              onChange={(status) => updateField('status', status as typeof values.status)}
              options={STATUS_OPTIONS}
              labelClassName={fieldLabelClassName}
            />
          </div>

          <div className="flex flex-wrap items-center justify-end gap-3 border-t border-border pt-4">
            <button type="button" onClick={cancel} className="rounded-full border border-border bg-surface px-6 py-2.5 font-body text-sm font-semibold text-text">
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void submit()}
              disabled={isSaving}
              className="rounded-full bg-admin-accent px-6 py-2.5 font-body text-sm font-semibold text-white disabled:opacity-50"
            >
              {isSaving ? 'Saving…' : isEditMode ? 'Save Changes' : 'Save Desk'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
