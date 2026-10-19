import { useNavigate } from 'react-router'
import { EmptyState } from '../../components/ui/EmptyState'
import { PlusIcon, RefreshCcwIcon } from '../../components/icons'
import { Pagination } from '../../components/Pagination'
import { PAGE_HEADER_GAP_CANCEL, PageContentLayout } from '../../components/PageContentLayout'
import { Collapsible } from '../../components/ui/Collapsible'
import { AsyncRegion } from '../../components/AsyncRegion'
import { PendingButton } from '../../components/ui/PendingButton'
import { TableSkeleton } from '../../components/ui/Skeleton'
import { PRESS_FEEDBACK_CLASS } from '../../components/ui/interactive'
import { usePageHeader } from '../../context/page-header-context'
import { RolesTable } from './Components/RolesTable'
import { useAdminRoles } from './hooks/use-admin-roles'

export function AdminRolesPage() {
  const navigate = useNavigate()
  const { roles, total, page, pageSize, goToNextPage, goToPrevPage, phase, isRefreshing, retry, isResyncing, resyncResult, resyncPermissions } =
    useAdminRoles()

  usePageHeader({ description: 'View roles and manage what each one is permitted to do' })

  return (
    <PageContentLayout
      header={
        <>
          <div className="flex w-full flex-wrap items-center justify-between gap-3">
            <h1 className="font-display text-xl font-bold md:text-2xl text-text">Roles &amp; Permissions</h1>
            <div className="flex flex-wrap items-center gap-3">
              <PendingButton
                pending={isResyncing}
                pendingLabel="Resyncing…"
                onClick={() => void resyncPermissions()}
                aria-label="Resync Permissions"
                className="flex items-center gap-2 rounded-full border border-border bg-surface p-btn-secondary font-body text-[13px] font-semibold text-text hover:bg-border-subtle disabled:opacity-50"
                title="Backfills any catalog permission a standard role is currently missing. Additive only — never revokes."
              >
                <RefreshCcwIcon className="size-3.5" />
                Resync Permissions
              </PendingButton>
              <button
                type="button"
                onClick={() => navigate('/admin/roles/new')}
                className={`flex items-center gap-2 rounded-full bg-admin-accent p-btn-primary font-body text-[13px] font-semibold text-white hover:bg-admin-accent/90 ${PRESS_FEEDBACK_CLASS}`}
              >
                <PlusIcon className="size-3.5" />
                Add Role
              </button>
            </div>
          </div>

          {/* Expands in place once a resync returns, instead of popping in. */}
          <Collapsible open={resyncResult !== undefined} closedClassName={PAGE_HEADER_GAP_CANCEL}>
          {resyncResult ? (
            <div className="flex w-full flex-col gap-2 rounded-xl border border-border bg-surface p-filter-panel">
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
          </Collapsible>
        </>
      }
    >
      <AsyncRegion
        phase={phase}
        isRefreshing={isRefreshing}
        skeleton={<TableSkeleton columns={5} rows={pageSize} label="Loading roles…" />}
        errorMessage="Something went wrong loading the roles. Please try again."
        onRetry={retry}
        isEmpty={roles.length === 0}
        empty={
          <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface py-16">
            <EmptyState message="No roles yet." />
          </div>
        }
      >
        <div className="flex flex-col gap-3">
          <RolesTable roles={roles} />
          <Pagination page={page} pageSize={pageSize} total={total} onPrev={goToPrevPage} onNext={goToNextPage} />
        </div>
      </AsyncRegion>
    </PageContentLayout>
  )
}
