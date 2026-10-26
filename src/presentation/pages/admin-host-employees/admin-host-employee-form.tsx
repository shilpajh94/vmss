import { useState } from 'react'
import { ChevronLeftIcon } from '../../components/icons'
import { FormSkeleton } from '../../components/ui/Skeleton'
import { PendingButton } from '../../components/ui/PendingButton'
import { SelectField } from '../../components/ui/SelectField'
import { TextField } from '../../components/ui/TextField'
import { usePageHeader } from '../../context/page-header-context'
import { useAdminHostEmployeeForm } from './hooks/use-admin-host-employee-form'

const fieldLabelClassName = 'text-[13px] font-bold uppercase text-text-secondary'

export function AdminHostEmployeeFormPage() {
  const [showPassword, setShowPassword] = useState(false)
  const {
    isEditMode,
    isLoading,
    errorMessage,
    retry,
    roles,
    branches,
    departments,
    createValues,
    createErrors,
    isSaving,
    updateCreateField,
    submitCreate,
    employee,
    departmentName,
    assignRoleId,
    setAssignRoleId,
    assignBranchId,
    setAssignBranchId,
    isAssigning,
    assignRole,
    revokingAssignmentId,
    revokeRole,
    cancel,
  } = useAdminHostEmployeeForm()

  const roleOptions = roles.map((role) => ({ value: role.id, label: role.name }))
  const branchOptions = branches.map((branch) => ({ value: branch.id, label: branch.name }))
  const branchNameById = new Map(branches.map((branch) => [branch.id, branch.name]))
  const departmentOptions = departments.map((department) => ({ value: department.id, label: department.name }))

  usePageHeader({ description: 'Registry of employees authorized to sponsor and host corporate visitors' })

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
            <h1 className="font-display text-xl font-bold md:text-2xl text-text">{isEditMode ? 'Manage Employee Access' : 'Add Employee'}</h1>
            <p className="font-body text-sm text-text-muted">
              {isEditMode
                ? 'View and manage this employee’s role and branch assignments'
                : 'Authorize a new employee to sponsor and host corporate visitors'}
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
          <FormSkeleton rows={isEditMode ? 3 : 4} label="Loading…" />
        ) : isEditMode && employee ? (
          <div className="flex w-full flex-col gap-8 rounded-2xl border border-border bg-surface p-10">
            <div className="flex flex-col gap-4">
              <h2 className="font-display text-base font-semibold text-text">Employee Details</h2>
              <p className="font-body text-[13px] text-text-muted">
                Name, email, and department are managed outside this system and can't be edited here.
              </p>
              <div className="flex flex-col gap-4 md:flex-row md:gap-6">
                <div className="flex-1">
                  <p className={fieldLabelClassName}>Employee Name</p>
                  <p className="mt-1.5 rounded-lg border border-border bg-border-subtle px-3 py-2 font-body text-sm text-text">
                    {employee.fullName}
                  </p>
                </div>
                <div className="flex-1">
                  <p className={fieldLabelClassName}>Email Address</p>
                  <p className="mt-1.5 rounded-lg border border-border bg-border-subtle px-3 py-2 font-body text-sm text-text">
                    {employee.email}
                  </p>
                </div>
                <div className="flex-1">
                  <p className={fieldLabelClassName}>Department</p>
                  <p className="mt-1.5 rounded-lg border border-border bg-border-subtle px-3 py-2 font-body text-sm text-text-muted">
                    {departmentName ?? 'Not assigned'}
                  </p>
                </div>
              </div>
            </div>

            <div className="h-px w-full bg-border" />

            <div className="flex flex-col gap-4">
              <h2 className="font-display text-base font-semibold text-text">Current Role Assignments</h2>
              {employee.branchRoles.length === 0 ? (
                <p className="font-body text-sm text-text-muted">No roles assigned yet.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {employee.branchRoles.map((role) => (
                    <div key={role.id} className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
                      <div className="flex flex-col gap-0.5">
                        <span className="font-body text-sm font-semibold text-text">{role.roleName}</span>
                        <span className="font-body text-xs text-text-muted">
                          {role.branchId ? branchNameById.get(role.branchId) ?? role.branchId : 'All branches'}
                        </span>
                      </div>
                      <PendingButton
                        onClick={() => void revokeRole(role.id)}
                        pending={revokingAssignmentId === role.id}
                        pendingLabel="Revoking…"
                        className="rounded-full border border-danger/30 bg-danger/10 px-3.5 py-1.5 font-body text-xs font-semibold text-danger disabled:opacity-50"
                      >
                        Revoke
                      </PendingButton>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="h-px w-full bg-border" />

            <div className="flex flex-col gap-4">
              <h2 className="font-display text-base font-semibold text-text">Assign a New Role</h2>
              <div className="flex flex-col gap-4 md:flex-row md:gap-6">
                <div className="flex-1">
                  <SelectField
                    label="Role"
                    value={assignRoleId}
                    onChange={setAssignRoleId}
                    options={roleOptions}
                    placeholder="Select role..."
                    labelClassName={fieldLabelClassName}
                  />
                </div>
                <div className="flex-1">
                  <SelectField
                    label="Branch (optional)"
                    value={assignBranchId}
                    onChange={setAssignBranchId}
                    options={branchOptions}
                    placeholder="All branches"
                    placeholderSelectable
                    labelClassName={fieldLabelClassName}
                  />
                </div>
              </div>
              <div className="flex justify-end">
                <PendingButton
                  onClick={() => void assignRole()}
                  disabled={!assignRoleId}
                  pending={isAssigning}
                  pendingLabel="Assigning…"
                  className="rounded-full bg-admin-accent px-6 py-2.5 font-body text-sm font-semibold text-on-accent disabled:opacity-50"
                >
                  Assign Role
                </PendingButton>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-end gap-3 border-t border-border pt-4">
              <button type="button" onClick={cancel} className="rounded-full border border-border bg-surface px-6 py-2.5 font-body text-sm font-semibold text-text">
                Done
              </button>
            </div>
          </div>
        ) : (
          <div className="flex w-full flex-col gap-8 rounded-2xl border border-border bg-surface p-10">
            <div className="flex flex-col gap-6">
              <TextField
                label="Employee Name"
                required
                value={createValues.fullName}
                onChange={(fullName) => updateCreateField('fullName', fullName)}
                error={createErrors.fullName}
                labelClassName={fieldLabelClassName}
              />
              <TextField
                label="Email Address"
                type="email"
                required
                value={createValues.email}
                onChange={(email) => updateCreateField('email', email)}
                error={createErrors.email}
                labelClassName={fieldLabelClassName}
              />
              <div className="flex flex-col gap-4 md:flex-row md:gap-6">
                <div className="flex-1">
                  <TextField
                    label="Employee Code"
                    placeholder="e.g. EMP-1024"
                    required
                    value={createValues.employeeCode}
                    onChange={(employeeCode) => updateCreateField('employeeCode', employeeCode)}
                    error={createErrors.employeeCode}
                    labelClassName={fieldLabelClassName}
                  />
                </div>
                <div className="flex-1">
                  <TextField
                    label="Designation"
                    value={createValues.designation ?? ''}
                    onChange={(designation) => updateCreateField('designation', designation || undefined)}
                    placeholder="e.g. Facilities Manager"
                    labelClassName={fieldLabelClassName}
                  />
                </div>
              </div>
              <div className="flex flex-col gap-4 md:flex-row md:gap-6">
                <div className="flex-1">
                  <TextField
                    label="Phone Number"
                    value={createValues.phoneNumber ?? ''}
                    onChange={(phoneNumber) => updateCreateField('phoneNumber', phoneNumber || undefined)}
                    placeholder="e.g. +1 555 000 1234"
                    labelClassName={fieldLabelClassName}
                  />
                </div>
                <div className="flex-1">
                  <SelectField
                    label="Department"
                    value={createValues.departmentId ?? ''}
                    onChange={(departmentId) => updateCreateField('departmentId', departmentId || undefined)}
                    options={departmentOptions}
                    placeholder="Select department (optional)..."
                    labelClassName={fieldLabelClassName}
                  />
                </div>
              </div>
              <div className="flex flex-col gap-4 md:flex-row md:gap-6">
                <div className="flex-1">
                  <SelectField
                    label="Role"
                    value={createValues.roleId ?? ''}
                    onChange={(roleId) => updateCreateField('roleId', roleId || undefined)}
                    options={roleOptions}
                    placeholder="Select role (optional)..."
                    labelClassName={fieldLabelClassName}
                  />
                </div>
                <div className="flex-1">
                  <SelectField
                    label="Branch"
                    value={createValues.branchId ?? ''}
                    onChange={(branchId) => updateCreateField('branchId', branchId || undefined)}
                    options={branchOptions}
                    placeholder="All branches"
                    placeholderSelectable
                    labelClassName={fieldLabelClassName}
                  />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <TextField
                  label="Password (optional)"
                  type={showPassword ? 'text' : 'password'}
                  value={createValues.password ?? ''}
                  onChange={(password) => updateCreateField('password', password || undefined)}
                  placeholder="At least 8 characters"
                  error={createErrors.password}
                  autoComplete="new-password"
                  labelClassName={fieldLabelClassName}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((current) => !current)}
                  aria-pressed={showPassword}
                  className="self-start font-body text-sm font-semibold text-secondary-accent"
                >
                  {showPassword ? 'Hide password' : 'Show password'}
                </button>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-end gap-3 border-t border-border pt-4">
              <button type="button" onClick={cancel} className="rounded-full border border-border bg-surface px-6 py-2.5 font-body text-sm font-semibold text-text">
                Cancel
              </button>
              <PendingButton
                onClick={() => void submitCreate()}
                pending={isSaving}
                pendingLabel="Saving…"
                className="rounded-full bg-admin-accent px-6 py-2.5 font-body text-sm font-semibold text-on-accent disabled:opacity-50"
              >
                Save Employee
              </PendingButton>
            </div>
          </div>
        )}
    </div>
  )
}
