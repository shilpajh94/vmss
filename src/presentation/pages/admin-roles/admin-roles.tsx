import { useNavigate } from 'react-router'
import { EmptyState } from '../../components/ui/EmptyState'
import { LoadingState } from '../../components/ui/LoadingState'
import { PlusIcon, RefreshCcwIcon } from '../../components/icons'
import { usePageHeader } from '../../context/page-header-context'
import { RolesTable } from './Components/RolesTable'
import { useAdminRoles } from './hooks/use-admin-roles'

export function AdminRolesPage() {
  const navigate = useNavigate()
  const { roles, isLoading, errorMessage, retry, isResyncing, resyncResult, resyncPermissions } = useAdminRoles()

  usePageHeader({ description: 'View roles and manage what each one is permitted to do' })

  return (
    <>
      <div className="flex w-full items-center justify-between">
        <h1 className="font-display text-2xl font-bold text-text">Roles &amp; Permissions</h1>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={retry}
            aria-label="Refresh"
            className="flex items-center gap-2 rounded-full border border-border bg-surface px-3.5 py-2.5 font-body text-[13px] font-semibold text-text"
          >
            <RefreshCcwIcon className="size-3.5" />
          </button>
          <button
            type="button"
            disabled={isResyncing}
            onClick={() => void resyncPermissions()}
            aria-label="Resync Permissions"
            className="flex items-center gap-2 rounded-full border border-border bg-surface px-3.5 py-2.5 font-body text-[13px] font-semibold text-text disabled:opacity-50"
            title="Backfills any catalog permission a standard role is currently missing. Additive only — never revokes."
          >
            <RefreshCcwIcon className="size-3.5" />
            {isResyncing ? 'Resyncing…' : 'Resync Permissions'}
          </button>
          <button
            type="button"
            onClick={() => navigate('/admin/roles/new')}
            className="flex items-center gap-2 rounded-full bg-admin-accent px-3.5 py-2.5 font-body text-[13px] font-semibold text-white"
          >
            <PlusIcon className="size-3.5" />
            Add Role
          </button>
        </div>
      </div>

      {resyncResult ? (
        <div className="flex w-full flex-col gap-2 rounded-xl border border-border bg-surface p-4">
          <p className="font-body text-sm font-semibold text-text">Resync result</p>
          {resyncResult.every((entry) => entry.grantedPermissionCodes.length === 0) ? (
            <p className="font-body text-xs text-text-muted">Every role already had everything the current permission catalog grants it.</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {resyncResult
                .filter((entry) => entry.grantedPermissionCodes.length > 0)
                .map((entry) => (
                  <li key={entry.roleName} className="font-body text-xs text-text-muted">
                    <span className="font-semibold text-text">{entry.roleName}</span>: granted {entry.grantedPermissionCodes.join(', ')}
                  </li>
                ))}
            </ul>
          )}
        </div>
      ) : null}

      {errorMessage ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-12 text-center">
          <p className="font-body text-sm text-danger">{errorMessage}</p>
          <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
            Try again
          </button>
        </div>
      ) : isLoading ? (
        <LoadingState label="Loading roles…" className="flex-1" />
      ) : roles.length === 0 ? (
        <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface">
          <EmptyState message="No roles yet." />
        </div>
      ) : (
        <RolesTable roles={roles} />
      )}
    </>
  )
}
