import { BackButton } from '../../components/BackButton'
import { Checkbox } from '../../components/ui/Checkbox'
import { FormSkeleton } from '../../components/ui/Skeleton'
import { PendingButton } from '../../components/ui/PendingButton'
import { TextField } from '../../components/ui/TextField'
import { TextareaField } from '../../components/ui/TextareaField'
import { usePageHeader } from '../../context/page-header-context'
import { useAdminRoleCreateForm } from './hooks/use-admin-role-create-form'
import { ErrorState } from '../../components/ui/ErrorState'

export function AdminRoleCreateFormPage() {
  const {
    permissions,
    name,
    setName,
    description,
    setDescription,
    selectedCodes,
    isLoading,
    errorMessage,
    nameError,
    retry,
    isSaving,
    togglePermission,
    submit,
    cancel,
  } = useAdminRoleCreateForm()

  usePageHeader({ breadcrumb: [{ label: 'Roles & Permissions' }, { label: 'Add Role', isActive: true }] })

  return (
    <>
      {errorMessage ? (
        <ErrorState message={errorMessage} onRetry={retry} />
      ) : isLoading ? (
        <FormSkeleton rows={6} columns={1} label="Loading permission catalog…" />
      ) : (
        <>
          <div className="flex items-center gap-4">
            <BackButton onClick={cancel} />
            <div className="flex flex-col gap-1">
              <h1 className="font-display text-xl font-bold md:text-2xl text-text">Add Role</h1>
              <p className="font-body text-sm text-text-muted">Name the role and choose what it is permitted to do.</p>
            </div>
          </div>

          <div className="flex w-full flex-col gap-4 rounded-2xl border border-border bg-surface p-4 md:p-6">
            <TextField
              label="Role name"
              required
              value={name}
              onChange={setName}
              error={nameError}
              placeholder="e.g. Front Desk Supervisor"
              maxLength={100}
            />
            <TextareaField label="Description" value={description} onChange={setDescription} placeholder="Optional" rows={2} maxLength={255} />
          </div>

          <div className="flex w-full flex-1 flex-col gap-3 rounded-2xl border border-border bg-surface p-4 md:p-6">
            {permissions.map((permission) => (
              <div key={permission.code} className="flex flex-col gap-0.5 border-b border-border-subtle pb-3 last:border-0 last:pb-0">
                <Checkbox checked={selectedCodes.has(permission.code)} onChange={(checked) => togglePermission(permission.code, checked)}>
                  <span className="font-body text-sm font-semibold text-text">{permission.code}</span>
                </Checkbox>
                <p className="pl-6 font-body text-xs text-text-muted">{permission.description}</p>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={cancel}
              className="rounded-full border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text"
            >
              Cancel
            </button>
            <PendingButton
              pending={isSaving}
              pendingLabel="Creating…"
              onClick={() => void submit()}
              className="rounded-full bg-admin-accent px-4 py-2 font-body text-[13px] font-semibold text-on-accent disabled:opacity-50"
            >
              Create Role
            </PendingButton>
          </div>
        </>
      )}
    </>
  )
}
