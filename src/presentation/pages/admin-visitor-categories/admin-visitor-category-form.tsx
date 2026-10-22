import { ChevronLeftIcon } from '../../components/icons'
import { FormSkeleton } from '../../components/ui/Skeleton'
import { PendingButton } from '../../components/ui/PendingButton'
import { SelectField } from '../../components/ui/SelectField'
import { TextField } from '../../components/ui/TextField'
import { TextareaField } from '../../components/ui/TextareaField'
import { usePageHeader } from '../../context/page-header-context'
import { BadgeColorField } from './Components/BadgeColorField'
import { useAdminVisitorCategoryForm } from './hooks/use-admin-visitor-category-form'

const NDA_REQUIREMENT_OPTIONS = [
  { value: 'digital', label: 'Yes (Digital)' },
  { value: 'signed_pdf', label: 'Yes (Signed PDF)' },
  { value: 'optional', label: 'Optional' },
  { value: 'none', label: 'Not Required' },
]

const ESCORT_REQUIREMENT_OPTIONS = [
  { value: 'self_escort', label: 'Self-Escort' },
  { value: 'access_logs_only', label: 'Access Logs Only' },
  { value: 'always_required', label: 'Always Required' },
  { value: 'gate_check_in_only', label: 'Gate Check-in Only' },
]

export function AdminVisitorCategoryFormPage() {
  const { isEditMode, isLoading, errorMessage, retry, values, errors, isSaving, updateField, submit, cancel } =
    useAdminVisitorCategoryForm()

  const fieldLabelClassName = 'text-[13px] font-bold uppercase text-text-secondary'

  usePageHeader({ description: 'Define visitor classifications, compliance procedures, security rules and physical pass designs' })

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
            <h1 className="font-display text-xl font-bold md:text-2xl text-text">{isEditMode ? 'Edit Category' : 'Add Category'}</h1>
            <p className="font-body text-sm text-text-muted">
              {isEditMode ? "Update this visitor category's classification and policy details" : 'Create a new visitor classification'}
            </p>
          </div>
        </div>

        {errorMessage ? (
          <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-border bg-surface p-4 md:p-6 text-center md:p-12">
            <p className="font-body text-sm text-danger">{errorMessage}</p>
            <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-on-accent">
              Try again
            </button>
          </div>
        ) : isLoading ? (
          <FormSkeleton rows={4} columns={2} label="Loading visitor category…" />
        ) : (
          <div className="flex w-full flex-col gap-8 rounded-2xl border border-border bg-surface p-10">
            <div className="flex flex-col gap-6">
              <div className="flex flex-col gap-4 md:flex-row md:gap-6">
                <div className="flex-1">
                  <TextField
                    label="Category Name"
                    required
                    value={values.name}
                    onChange={(name) => updateField('name', name)}
                    error={errors.name}
                    labelClassName={fieldLabelClassName}
                  />
                </div>
                <div className="flex-1">
                  <TextField
                    label="Category Code"
                    required
                    value={values.code}
                    onChange={(code) => updateField('code', code)}
                    error={errors.code}
                    labelClassName={fieldLabelClassName}
                  />
                </div>
              </div>
              <TextareaField
                label="Description"
                value={values.description ?? ''}
                onChange={(description) => updateField('description', description || undefined)}
                placeholder="Brief summary of who this category covers..."
                rows={3}
                labelClassName={fieldLabelClassName}
              />
              <BadgeColorField
                value={values.badgeColor}
                onChange={(badgeColor) => updateField('badgeColor', badgeColor)}
                labelClassName={fieldLabelClassName}
              />
              <div className="flex flex-col gap-4 md:flex-row md:gap-6">
                <div className="flex-1">
                  <SelectField
                    label="NDA Required"
                    value={values.ndaRequirement ?? ''}
                    onChange={(ndaRequirement) => updateField('ndaRequirement', (ndaRequirement || undefined) as typeof values.ndaRequirement)}
                    options={NDA_REQUIREMENT_OPTIONS}
                    placeholder="Select NDA requirement..."
                    labelClassName={fieldLabelClassName}
                  />
                </div>
                <div className="flex-1">
                  <SelectField
                    label="Escort Required"
                    value={values.escortRequirement ?? ''}
                    onChange={(escortRequirement) =>
                      updateField('escortRequirement', (escortRequirement || undefined) as typeof values.escortRequirement)
                    }
                    options={ESCORT_REQUIREMENT_OPTIONS}
                    placeholder="Select escort requirement..."
                    labelClassName={fieldLabelClassName}
                  />
                </div>
              </div>
              <TextField
                label="Max Duration (minutes)"
                type="number"
                value={values.maxDurationMinutes !== undefined ? String(values.maxDurationMinutes) : ''}
                onChange={(value) => updateField('maxDurationMinutes', value ? Number(value) : undefined)}
                placeholder="e.g. 480"
                labelClassName={fieldLabelClassName}
              />
            </div>

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
                {isEditMode ? 'Save Changes' : 'Save Category'}
              </PendingButton>
            </div>
          </div>
        )}
    </div>
  )
}
