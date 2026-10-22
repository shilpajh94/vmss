import { ChevronLeftIcon } from '../../components/icons'
import { FormSkeleton } from '../../components/ui/Skeleton'
import { PendingButton } from '../../components/ui/PendingButton'
import { SelectField } from '../../components/ui/SelectField'
import { TextField } from '../../components/ui/TextField'
import { TextareaField } from '../../components/ui/TextareaField'
import { ToggleSwitch } from '../../components/ui/ToggleSwitch'
import { usePageHeader } from '../../context/page-header-context'
import { useAdminDepartmentForm } from './hooks/use-admin-department-form'

export function AdminDepartmentFormPage() {
  const {
    isEditMode,
    branches,
    employees,
    isLoading,
    errorMessage,
    retry,
    values,
    errors,
    isSaving,
    updateField,
    submit,
    cancel,
  } = useAdminDepartmentForm()

  usePageHeader({ description: 'Organize company departments, associate branch operations, and heads of dept' })

  const branchOptions = branches.map((branch) => ({ value: branch.id, label: branch.name }))
  const employeeOptions = employees.map((employee) => ({ value: employee.id, label: employee.fullName }))
  const fieldLabelClassName = 'text-[13px] font-bold uppercase text-text-secondary'

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
          <h1 className="font-display text-xl font-bold md:text-2xl text-text">{isEditMode ? 'Edit Department' : 'Add Department'}</h1>
          <p className="font-body text-sm text-text-muted">
            {isEditMode
              ? "Update this operational division's details"
              : 'Create a new operational division inside your workplace directory'}
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
          <FormSkeleton rows={4} columns={1} label="Loading department…" />
        ) : (
          <div className="flex w-full flex-col gap-8 rounded-2xl border border-border bg-surface p-10">
            <div className="flex flex-col gap-6">
              <div className="flex flex-col gap-4 md:flex-row md:gap-6">
                <div className="flex-1">
                  <TextField
                    label="Department Name"
                    required
                    value={values.name}
                    onChange={(name) => updateField('name', name)}
                    error={errors.name}
                    maxLength={255}
                    labelClassName={fieldLabelClassName}
                  />
                </div>
                <div className="flex-1">
                  <SelectField
                    label="Branch"
                    required
                    value={values.branchId}
                    onChange={(branchId) => updateField('branchId', branchId)}
                    options={branchOptions}
                    disabled={isEditMode}
                    placeholder="Select target branch..."
                    error={errors.branchId}
                    labelClassName={fieldLabelClassName}
                  />
                </div>
              </div>
              <TextField
                label="Department Code"
                required
                value={values.code}
                onChange={(code) => updateField('code', code)}
                error={errors.code}
                maxLength={50}
                labelClassName={fieldLabelClassName}
              />
              <SelectField
                label="Head of Department"
                value={values.headOfDepartmentUserId ?? ''}
                onChange={(headOfDepartmentUserId) => updateField('headOfDepartmentUserId', headOfDepartmentUserId)}
                options={employeeOptions}
                placeholder="Select employee..."
                labelClassName={fieldLabelClassName}
              />
              <TextareaField
                label="Description"
                value={values.description ?? ''}
                onChange={(description) => updateField('description', description)}
                maxLength={2000}
                placeholder="Brief summary of this department's function, coverage, and workspace rules..."
                rows={3}
                labelClassName={fieldLabelClassName}
              />
              <div className="flex items-center justify-between py-2">
                <div className="flex flex-col gap-1">
                  <p className="font-body text-sm font-bold uppercase text-text">Department Status</p>
                  <p className="font-body text-[13px] text-text-muted">Set whether this department is active and accessible across workspace branches</p>
                </div>
                <ToggleSwitch
                  label={values.isActive ? 'Active' : 'Inactive'}
                  checked={values.isActive}
                  onChange={(checked) => updateField('isActive', checked)}
                />
              </div>
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
                {isEditMode ? 'Save Changes' : 'Save Department'}
              </PendingButton>
            </div>
          </div>
        )}
    </div>
  )
}
