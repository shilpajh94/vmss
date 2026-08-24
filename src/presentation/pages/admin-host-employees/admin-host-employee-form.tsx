import { AdminSidebar } from '../../components/AdminSidebar'
import { AdminTopBar } from '../../components/AdminTopBar'
import { ChevronLeftIcon } from '../../components/icons'
import { LoadingState } from '../../components/ui/LoadingState'
import { SelectField } from '../../components/ui/SelectField'
import { TextField } from '../../components/ui/TextField'
import { useAdminHostEmployeeForm } from './hooks/use-admin-host-employee-form'

const fieldLabelClassName = 'text-[13px] font-bold uppercase text-[#475569]'

export function AdminHostEmployeeFormPage() {
  const {
    isEditMode,
    currentUser,
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

  return (
    <div className="flex min-h-screen w-full items-stretch bg-bg">
      <AdminSidebar activeItem="host-employees" />

      <div className="flex flex-1 flex-col">
        <AdminTopBar description="Registry of employees authorized to sponsor and host corporate visitors" currentUser={currentUser} />

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
                <h1 className="font-display text-2xl font-bold text-text">{isEditMode ? 'Manage Host Employee Access' : 'Add Host Employee'}</h1>
                <p className="font-body text-sm text-text-muted">
                  {isEditMode
                    ? 'View and manage this employee’s role and branch assignments'
                    : 'Authorize a new employee to sponsor and host corporate visitors'}
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
            ) : isEditMode && employee ? (
              <div className="flex w-full flex-col gap-8 rounded-2xl border border-border bg-surface p-10">
                <div className="flex flex-col gap-4">
                  <h2 className="font-display text-base font-semibold text-text">Employee Details</h2>
                  <p className="font-body text-[13px] text-text-muted">
                    Name, email, and department are managed outside this system and can't be edited here.
                  </p>
                  <div className="flex gap-6">
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
                          <button
                            type="button"
                            onClick={() => void revokeRole(role.id)}
                            disabled={revokingAssignmentId === role.id}
                            className="rounded-full border border-danger/30 bg-danger/10 px-3.5 py-1.5 font-body text-xs font-semibold text-danger disabled:opacity-50"
                          >
                            {revokingAssignmentId === role.id ? 'Revoking…' : 'Revoke'}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="h-px w-full bg-border" />

                <div className="flex flex-col gap-4">
                  <h2 className="font-display text-base font-semibold text-text">Assign a New Role</h2>
                  <div className="flex gap-6">
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
                        labelClassName={fieldLabelClassName}
                      />
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={() => void assignRole()}
                      disabled={!assignRoleId || isAssigning}
                      className="rounded-full bg-admin-accent px-6 py-2.5 font-body text-sm font-semibold text-white disabled:opacity-50"
                    >
                      {isAssigning ? 'Assigning…' : 'Assign Role'}
                    </button>
                  </div>
                </div>

                <div className="flex items-center justify-end gap-3 border-t border-border pt-4">
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
                  <div className="flex gap-6">
                    <div className="flex-1">
                      <TextField
                        label="Employee Code"
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
                  <div className="flex gap-6">
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
                  <div className="flex gap-6">
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
                        labelClassName={fieldLabelClassName}
                      />
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-end gap-3 border-t border-border pt-4">
                  <button type="button" onClick={cancel} className="rounded-full border border-border bg-surface px-6 py-2.5 font-body text-sm font-semibold text-text">
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={() => void submitCreate()}
                    disabled={isSaving}
                    className="rounded-full bg-admin-accent px-6 py-2.5 font-body text-sm font-semibold text-white disabled:opacity-50"
                  >
                    {isSaving ? 'Saving…' : 'Save Host Employee'}
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
