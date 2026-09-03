import { AdminSidebar } from '../../components/AdminSidebar'
import { AdminTopBar } from '../../components/AdminTopBar'
import { KanbanColumn } from '../../components/invitation-board/KanbanColumn'
import { DenyInvitationModal } from '../../components/invitation-board/DenyInvitationModal'
import { RescheduleInvitationModal } from '../../components/invitation-board/RescheduleInvitationModal'
import { DelegateInvitationModal } from '../../components/invitation-board/DelegateInvitationModal'
import { LoadingState } from '../../components/ui/LoadingState'
import { RefreshCcwIcon, SearchGlyphIcon } from '../../components/icons'
import { useAdminInvitations } from './hooks/use-admin-invitations'

const EMPTY_MESSAGES: Record<string, string> = {
  requested: 'No requested visits',
  approved: 'No approved visits',
  checked_in: 'No checked-in visitors today',
  denied: 'No denied visits',
}

export function AdminInvitationsPage() {
  const {
    currentUser,
    columns,
    isLoading,
    errorMessage,
    search,
    setSearch,
    refresh,
    approve,
    approvingId,
    expandedId,
    toggleExpand,
    invitationDetails,
    loadingDetailId,
    roleNameById,
    hostEmployees,
    employeeNameById,
    reschedule,
    reschedulingId,
    delegate,
    delegatingId,
    pendingDenyId,
    requestDeny,
    cancelDeny,
    confirmDeny,
    denyingId,
    pendingRescheduleId,
    requestReschedule,
    cancelReschedule,
    pendingDelegateId,
    requestDelegate,
    cancelDelegate,
    pendingDelegateDetail,
  } = useAdminInvitations()

  return (
    <div className="flex min-h-screen w-full items-stretch bg-bg">
      <AdminSidebar activeItem="invitations" />

      <div className="flex flex-1 flex-col">
        <AdminTopBar description="Monitor visitor invitations, approval status, and check-in progress" currentUser={currentUser} />

        <main className="flex flex-1 flex-col gap-6 p-8">
          <div className="flex w-full items-center justify-between">
            <h1 className="font-display text-2xl font-bold text-text">Invitations</h1>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 rounded-full border border-border bg-surface px-3.5 py-2.5">
                <SearchGlyphIcon className="size-3.5 shrink-0 text-text-faint" />
                <input
                  type="text"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search visitor, tracking ID..."
                  className="w-56 bg-transparent font-body text-[13px] text-text placeholder:text-text-faint focus:outline-none"
                />
              </div>
              <button
                type="button"
                onClick={refresh}
                className="flex items-center gap-2 rounded-full border border-border bg-surface px-3.5 py-2.5 font-body text-[13px] font-semibold text-text"
              >
                <RefreshCcwIcon className="size-3.5" />
                Refresh
              </button>
            </div>
          </div>

          {errorMessage ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-12 text-center">
              <p className="font-body text-sm text-danger">{errorMessage}</p>
              <button type="button" onClick={refresh} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
                Try again
              </button>
            </div>
          ) : isLoading ? (
            <LoadingState label="Loading invitations…" className="flex-1" />
          ) : (
            <div className="flex w-full flex-1 items-start gap-4">
              {columns.map((column) => (
                <KanbanColumn
                  key={column.status}
                  status={column.status}
                  label={column.label}
                  requests={column.requests}
                  emptyMessage={EMPTY_MESSAGES[column.status]}
                  onDrop={column.status === 'approved' ? approve : column.status === 'denied' ? requestDeny : undefined}
                  approvingId={approvingId}
                  expandedId={expandedId}
                  onToggleExpand={toggleExpand}
                  invitationDetails={invitationDetails}
                  loadingDetailId={loadingDetailId}
                  roleNameById={roleNameById}
                  employeeNameById={employeeNameById}
                  onRescheduleClick={requestReschedule}
                  onDelegateClick={requestDelegate}
                />
              ))}
            </div>
          )}
        </main>
      </div>

      <DenyInvitationModal isOpen={pendingDenyId !== undefined} isDenying={denyingId !== undefined} onConfirm={confirmDeny} onCancel={cancelDeny} />

      <RescheduleInvitationModal
        isOpen={pendingRescheduleId !== undefined}
        isRescheduling={reschedulingId !== undefined}
        onConfirm={(preferredVisitDate, preferredVisitTime) =>
          pendingRescheduleId && reschedule(pendingRescheduleId, preferredVisitDate, preferredVisitTime)
        }
        onCancel={cancelReschedule}
      />

      <DelegateInvitationModal
        isOpen={pendingDelegateId !== undefined}
        isDelegating={delegatingId !== undefined}
        approverRoleId={pendingDelegateDetail?.currentApprovalStep?.approverRoleId}
        roleNameById={roleNameById}
        hostEmployees={hostEmployees}
        onConfirm={(delegateUserId) => pendingDelegateId && delegate(pendingDelegateId, delegateUserId)}
        onCancel={cancelDelegate}
      />
    </div>
  )
}
