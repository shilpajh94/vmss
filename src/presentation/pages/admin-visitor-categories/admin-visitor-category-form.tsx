import { AdminSidebar } from '../../components/AdminSidebar'
import { AdminTopBar } from '../../components/AdminTopBar'
import { ChevronLeftIcon } from '../../components/icons'
import { LoadingState } from '../../components/ui/LoadingState'
import { TextField } from '../../components/ui/TextField'
import { TextareaField } from '../../components/ui/TextareaField'
import { BadgeColorField } from './Components/BadgeColorField'
import { useAdminVisitorCategoryForm } from './hooks/use-admin-visitor-category-form'

export function AdminVisitorCategoryFormPage() {
  const { isEditMode, currentUser, isLoading, errorMessage, retry, values, errors, isSaving, updateField, submit, cancel } =
    useAdminVisitorCategoryForm()

  const fieldLabelClassName = 'text-[13px] font-bold uppercase text-[#475569]'

  return (
    <div className="flex min-h-screen w-full items-stretch bg-bg">
      <AdminSidebar activeItem="visitor-categories" />

      <div className="flex flex-1 flex-col">
        <AdminTopBar
          description="Define visitor classifications, compliance procedures, security rules and physical pass designs"
          currentUser={currentUser}
        />

        <main className="flex flex-1 flex-col items-center p-8">
          <div className="flex w-full max-w-[1160px] flex-col gap-6">
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
                <h1 className="font-display text-2xl font-bold text-text">{isEditMode ? 'Edit Category' : 'Add Category'}</h1>
                <p className="font-body text-sm text-text-muted">
                  {isEditMode ? "Update this visitor category's classification and policy details" : 'Create a new visitor classification'}
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
                  <TextField
                    label="Category Name"
                    required
                    value={values.name}
                    onChange={(name) => updateField('name', name)}
                    error={errors.name}
                    labelClassName={fieldLabelClassName}
                  />
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
                  <div className="flex gap-6">
                    <div className="flex-1">
                      <TextField
                        label="NDA Required"
                        value={values.ndaRequired ?? ''}
                        onChange={(ndaRequired) => updateField('ndaRequired', ndaRequired || undefined)}
                        placeholder="e.g. Yes (Digital)"
                        labelClassName={fieldLabelClassName}
                      />
                    </div>
                    <div className="flex-1">
                      <TextField
                        label="Escort Required"
                        value={values.escortRequired ?? ''}
                        onChange={(escortRequired) => updateField('escortRequired', escortRequired || undefined)}
                        placeholder="e.g. Required (Always)"
                        labelClassName={fieldLabelClassName}
                      />
                    </div>
                  </div>
                  <TextField
                    label="Max Duration"
                    value={values.maxDuration ?? ''}
                    onChange={(maxDuration) => updateField('maxDuration', maxDuration || undefined)}
                    placeholder="e.g. 8 Hours"
                    labelClassName={fieldLabelClassName}
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
                    {isSaving ? 'Saving…' : isEditMode ? 'Save Changes' : 'Save Category'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
