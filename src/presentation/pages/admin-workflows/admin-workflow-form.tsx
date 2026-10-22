import { ChevronLeftIcon, PlusIcon, TrashIcon } from '../../components/icons'
import { FormSkeleton } from '../../components/ui/Skeleton'
import { PendingButton } from '../../components/ui/PendingButton'
import { SelectField } from '../../components/ui/SelectField'
import { usePageHeader } from '../../context/page-header-context'
import { useAdminWorkflowForm } from './hooks/use-admin-workflow-form'

export function AdminWorkflowFormPage() {
  const {
    isEditMode,
    categoryOptions,
    roles,
    isLoading,
    errorMessage,
    retry,
    selectedCategoryId,
    levels,
    errors,
    isSaving,
    updateCategory,
    addLevel,
    removeLevel,
    updateLevelApprover,
    submit,
    cancel,
  } = useAdminWorkflowForm()

  const categorySelectOptions = categoryOptions.map((category) => ({ value: category.id, label: category.name }))
  const roleSelectOptions = roles.map((role) => ({ value: role.id, label: role.name }))
  const fieldLabelClassName = 'text-[13px] font-bold uppercase text-text-secondary'

  usePageHeader({ description: 'Configure automated visitor check-in, alert triggers, and compliance workflows' })

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
          <h1 className="font-display text-xl font-bold md:text-2xl text-text">{isEditMode ? 'Edit Workflow' : 'Add Workflow'}</h1>
        </div>

        {errorMessage ? (
          <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-border bg-surface p-4 md:p-6 text-center md:p-12">
            <p className="font-body text-sm text-danger">{errorMessage}</p>
            <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-on-accent">
              Try again
            </button>
          </div>
        ) : isLoading ? (
          <FormSkeleton rows={4} columns={1} label="Loading workflow…" />
        ) : (
          <div className="flex w-full flex-col gap-8 rounded-2xl border border-border bg-surface p-10">
            <div className="flex flex-col gap-6">
              <div className="max-w-md">
                <SelectField
                  label="Visitor Category"
                  required
                  value={selectedCategoryId}
                  onChange={updateCategory}
                  options={categorySelectOptions}
                  placeholder="Select visitor category..."
                  error={errors.categoryId}
                  disabled={isEditMode}
                  labelClassName={fieldLabelClassName}
                />
              </div>

              <div className="flex flex-col gap-1">
                <h2 className="font-body text-sm font-bold text-text">Approval Levels</h2>
                <p className="font-body text-[13px] text-text-muted">Staff will approve sequentially in the order listed below</p>
              </div>

              <div className="flex flex-col gap-3">
                {levels.map((level, index) => (
                  <div key={index} className="flex items-center gap-3">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-secondary-accent/15 font-body text-xs font-bold text-secondary-accent">
                      {index + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <SelectField
                        label={`Level ${index + 1} approver`}
                        labelClassName="sr-only"
                        required
                        disabled={index === 0}
                        value={level.approverRoleId}
                        onChange={(approverRoleId) => updateLevelApprover(index, approverRoleId)}
                        options={roleSelectOptions}
                        placeholder="Select approver role..."
                        error={errors.levels?.[index]}
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => removeLevel(index)}
                      disabled={index === 0 || levels.length <= 1}
                      aria-label={`Remove level ${index + 1}`}
                      className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-danger/15 text-danger disabled:opacity-40"
                    >
                      <TrashIcon className="size-3.5" />
                    </button>
                  </div>
                ))}
              </div>

              <button
                type="button"
                onClick={addLevel}
                className="flex w-fit items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text"
              >
                <PlusIcon className="size-3.5" />
                Add Level
              </button>
            </div>

            <div className="flex flex-wrap items-center justify-end gap-3 border-t border-border pt-4">
              <button
                type="button"
                onClick={cancel}
                className="rounded-full border border-border bg-surface px-6 py-2.5 font-body text-sm font-semibold text-text"
              >
                Cancel
              </button>
              <PendingButton
                onClick={() => void submit()}
                pending={isSaving}
                pendingLabel="Saving…"
                className="rounded-full bg-admin-accent px-6 py-2.5 font-body text-sm font-semibold text-on-accent disabled:opacity-50"
              >
                Save Workflow
              </PendingButton>
            </div>
          </div>
        )}
    </div>
  )
}
