import { BackButton } from '../../components/BackButton'
import { Checkbox } from '../../components/ui/Checkbox'
import { FormSkeleton } from '../../components/ui/Skeleton'
import { PendingButton } from '../../components/ui/PendingButton'
import { usePageHeader } from '../../context/page-header-context'
import { useAdminRolePermissionsForm } from './hooks/use-admin-role-permissions-form'

export function AdminRolePermissionsFormPage() {
  const { role, permissions, selectedCodes, isLoading, errorMessage, retry, isSaving, togglePermission, submit, cancel } =
    useAdminRolePermissionsForm()

  usePageHeader({ breadcrumb: [{ label: 'Roles & Permissions' }, { label: role?.name ?? '...', isActive: true }] })

  return (
    <>
      {errorMessage ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-6 text-center md:p-12">
          <p className="font-body text-sm text-danger">{errorMessage}</p>
          <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-on-accent">
            Try again
          </button>
        </div>
      ) : isLoading ? (
        <FormSkeleton rows={6} columns={1} label="Loading role…" />
      ) : (
        <>
          <div className="flex items-center gap-4">
            <BackButton onClick={cancel} />
            <div className="flex flex-col gap-1">
              <h1 className="font-display text-xl font-bold md:text-2xl text-text">{role?.name}</h1>
              <p className="font-body text-sm text-text-muted">{role?.description ?? 'Choose what this role is permitted to do.'}</p>
            </div>
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
              pendingLabel="Saving…"
              onClick={() => void submit()}
              className="rounded-full bg-admin-accent px-4 py-2 font-body text-[13px] font-semibold text-on-accent disabled:opacity-50"
            >
              Save Permissions
            </PendingButton>
          </div>
        </>
      )}
    </>
  )
}
