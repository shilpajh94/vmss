import type { FormEvent } from 'react'
import { FormSkeleton } from '../../components/ui/Skeleton'
import { PendingButton } from '../../components/ui/PendingButton'
import { TextField } from '../../components/ui/TextField'
import { TextareaField } from '../../components/ui/TextareaField'
import { ToggleSwitch } from '../../components/ui/ToggleSwitch'
import { usePageHeader } from '../../context/page-header-context'
import { useAdminKioskForm } from './hooks/use-admin-kiosk-form'
import { ErrorState } from '../../components/ui/ErrorState'
import { FormPageHeader } from '../../components/FormPageHeader'

export function AdminKioskFormPage() {
  const { isEditMode, isLoading, errorMessage, retry, values, errors, isSaving, updateField, submit, cancel } = useAdminKioskForm()

  const fieldLabelClassName = 'text-[13px] font-bold uppercase text-text-secondary'

  usePageHeader({ description: 'Manage the company-wide check-in kiosks' })

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    void submit()
  }

  return (
    <div className="mx-auto flex w-full max-w-[1160px] flex-col gap-6">
      <FormPageHeader title={isEditMode ? 'Edit Kiosk' : 'Add Kiosk'} description={isEditMode ? "Update this kiosk's details" : 'Register a new check-in kiosk'} onBack={cancel} />

      {errorMessage ? (
        <ErrorState message={errorMessage} onRetry={retry} />
      ) : isLoading ? (
        <FormSkeleton rows={3} columns={1} label="Loading kiosk…" />
      ) : (
        <form onSubmit={handleSubmit} className="flex w-full flex-col gap-8 rounded-2xl border border-border bg-surface p-10">
          <div className="flex flex-col gap-6">
            <TextField
              label="Name"
              maxLength={255}
              required
              value={values.name}
              onChange={(name) => updateField('name', name)}
              error={errors.name}
              labelClassName={fieldLabelClassName}
            />
            <TextareaField
              label="Description"
              maxLength={2000}
              value={values.description ?? ''}
              onChange={(description) => updateField('description', description)}
              error={errors.description}
              labelClassName={fieldLabelClassName}
            />
            <ToggleSwitch label="Active" checked={values.isActive} onChange={(isActive) => updateField('isActive', isActive)} />
          </div>

          <div className="flex flex-wrap items-center justify-end gap-3 border-t border-border pt-4">
            <button type="button" onClick={cancel} className="rounded-full border border-border bg-surface px-6 py-2.5 font-body text-sm font-semibold text-text">
              Cancel
            </button>
            <PendingButton
              type="submit"
              pending={isSaving}
              pendingLabel="Saving…"
              className="rounded-full bg-admin-accent px-6 py-2.5 font-body text-sm font-semibold text-on-accent disabled:opacity-50"
            >
              {isEditMode ? 'Save Changes' : 'Save Kiosk'}
            </PendingButton>
          </div>
        </form>
      )}
    </div>
  )
}
