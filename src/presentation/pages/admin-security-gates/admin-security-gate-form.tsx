import { ChevronLeftIcon } from '../../components/icons'
import { LoadingState } from '../../components/ui/LoadingState'
import { SelectField } from '../../components/ui/SelectField'
import { TextField } from '../../components/ui/TextField'
import { ToggleSwitch } from '../../components/ui/ToggleSwitch'
import { usePageHeader } from '../../context/page-header-context'
import { useAdminSecurityGateForm } from './hooks/use-admin-security-gate-form'

const GATE_TYPE_OPTIONS = [
  { value: 'both', label: 'Entry & Exit' },
  { value: 'entry', label: 'Entry Only' },
  { value: 'exit', label: 'Exit Only' },
]

export function AdminSecurityGateFormPage() {
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
  } = useAdminSecurityGateForm()

  const buildingOptions = buildings.map((building) => ({ value: building.id, label: building.name }))
  const fieldLabelClassName = 'text-[13px] font-bold uppercase text-[#475569]'

  usePageHeader({ description: 'Configure hardware gates and turnstiles' })

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
          <h1 className="font-display text-2xl font-bold text-text">{isEditMode ? 'Edit Gate' : 'Register Gate'}</h1>
          <p className="font-body text-sm text-text-muted">
            {isEditMode ? "Update this gate's access-control details" : 'Register a new security gate or turnstile'}
          </p>
        </div>
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
        <div className="flex w-full flex-col gap-8 rounded-2xl border border-border bg-surface p-10">
          <div className="flex flex-col gap-6">
            <div className="flex gap-6">
              <div className="flex-1">
                <TextField
                  label="Gate Name/ID"
                  required
                  value={values.name}
                  onChange={(name) => updateField('name', name)}
                  error={errors.name}
                  labelClassName={fieldLabelClassName}
                />
              </div>
              <div className="flex-1">
                <TextField
                  label="Gate Code"
                  required
                  value={values.code}
                  onChange={(code) => updateField('code', code)}
                  error={errors.code}
                  labelClassName={fieldLabelClassName}
                />
              </div>
            </div>
            <div className="flex gap-6">
              <div className="flex-1">
                <SelectField
                  label="Building"
                  required
                  value={values.buildingId}
                  onChange={(buildingId) => updateField('buildingId', buildingId)}
                  options={buildingOptions}
                  placeholder="Select building..."
                  error={errors.buildingId}
                  labelClassName={fieldLabelClassName}
                />
              </div>
              <div className="flex-1">
                <SelectField
                  label="Gate Type"
                  required
                  value={values.gateType}
                  onChange={(gateType) => updateField('gateType', gateType as typeof values.gateType)}
                  options={GATE_TYPE_OPTIONS}
                  labelClassName={fieldLabelClassName}
                />
              </div>
            </div>
            <ToggleSwitch
              label="High Security"
              checked={values.highSecurity}
              onChange={(highSecurity) => updateField('highSecurity', highSecurity)}
            />
          </div>

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
              {isSaving ? 'Saving…' : isEditMode ? 'Save Changes' : 'Save Gate'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
