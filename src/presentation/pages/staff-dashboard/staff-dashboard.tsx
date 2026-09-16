import { DashboardSidebar } from '../../components/DashboardSidebar'
import { ReceptionSidebar } from '../../components/ReceptionSidebar'
import { LoadingState } from '../../components/ui/LoadingState'
import { KanbanColumn } from '../../components/invitation-board/KanbanColumn'
import { DenyInvitationModal } from '../../components/invitation-board/DenyInvitationModal'
import { RescheduleInvitationModal } from '../../components/invitation-board/RescheduleInvitationModal'
import { DelegateInvitationModal } from '../../components/invitation-board/DelegateInvitationModal'
import { EditInvitationModal } from '../../components/invitation-board/EditInvitationModal'
import { VisitorInfoModal } from '../../components/invitation-board/VisitorInfoModal'
import { SearchActionBar } from './Components/SearchActionBar'
import { WorkspaceHeader } from './Components/WorkspaceHeader'
import { useStaffDashboard } from './hooks/use-staff-dashboard'

const EMPTY_MESSAGES: Record<string, string> = {
  requested: 'No requested visits',
  approved: 'No approved visits',
  checked_in: 'No checked-in visitors today',
  denied: 'No denied visits',
}

export function StaffDashboardPage() {
  const {
    currentUser,
    columns,
    isLoading,
    errorMessage,
    search,
    setSearch,
    purposeFilter,
    setPurposeFilter,
    purposeOptions,
    registrationTypeFilter,
    setRegistrationTypeFilter,
    refresh,
    signOut,
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
    edit,
    editingId,
    requestEdit,
    cancelEdit,
    pendingEditId,
    pendingEditDetail,
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
    approveAndDelegate,
    approvingAndDelegatingId,
    pendingApproveAndDelegateId,
    requestApproveAndDelegate,
    cancelApproveAndDelegate,
    nextStepCandidates,
    isLoadingNextStepCandidates,
    workflowRulesByCategory,
    visitorInfoId,
    viewVisitorInfo,
    closeVisitorInfo,
  } = useStaffDashboard()

  return (
    <div className="flex min-h-screen w-full items-stretch bg-bg">
      {currentUser?.isReception ? <ReceptionSidebar activeItem="visits" /> : <DashboardSidebar activeItem="all-visitors" />}

      <main className="flex flex-1 flex-col gap-6 p-8">
        <WorkspaceHeader currentUser={currentUser} onRefresh={refresh} onSignOut={signOut} />
        <SearchActionBar
          search={search}
          onSearchChange={setSearch}
          purposeFilter={purposeFilter}
          onPurposeFilterChange={setPurposeFilter}
          purposeOptions={purposeOptions}
          registrationTypeFilter={registrationTypeFilter}
          onRegistrationTypeFilterChange={setRegistrationTypeFilter}
        />

        {errorMessage ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-12 text-center">
            <p className="font-body text-sm text-danger">{errorMessage}</p>
            <button type="button" onClick={refresh} className="rounded-lg bg-secondary-accent px-4 py-2 font-body text-sm font-semibold text-white">
              Try again
            </button>
          </div>
        ) : isLoading ? (
          <LoadingState label="Loading visit requests…" className="flex-1" />
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
                workflowRulesByCategory={workflowRulesByCategory}
                onRescheduleClick={requestReschedule}
                onDelegateClick={requestDelegate}
                onApproveAndDelegateClick={requestApproveAndDelegate}
                onApproveClick={approve}
                onEditClick={requestEdit}
                onVisitorInfoClick={viewVisitorInfo}
              />
            ))}
          </div>
        )}
      </main>

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
        stepOrder={pendingDelegateDetail?.currentApprovalStep?.stepOrder}
        roleNameById={roleNameById}
        hostEmployees={hostEmployees}
        branchId={pendingDelegateDetail?.branchId}
        onConfirm={(delegateUserId) => pendingDelegateId && delegate(pendingDelegateId, delegateUserId)}
        onCancel={cancelDelegate}
      />

      <DelegateInvitationModal
        isOpen={pendingApproveAndDelegateId !== undefined}
        isDelegating={approvingAndDelegatingId !== undefined}
        mode="approve-and-delegate"
        isLoadingCandidates={isLoadingNextStepCandidates}
        hostEmployees={nextStepCandidates}
        onConfirm={(delegateUserId) => pendingApproveAndDelegateId && approveAndDelegate(pendingApproveAndDelegateId, delegateUserId)}
        onCancel={cancelApproveAndDelegate}
      />

      <EditInvitationModal
        isOpen={pendingEditId !== undefined}
        isSaving={editingId !== undefined}
        detail={pendingEditDetail}
        workflowRulesByCategory={workflowRulesByCategory}
        hostEmployees={hostEmployees}
        onConfirm={(fields) => pendingEditId && edit(pendingEditId, fields)}
        onCancel={cancelEdit}
      />

      <VisitorInfoModal
        isOpen={visitorInfoId !== undefined}
        isLoading={visitorInfoId !== undefined && !invitationDetails[visitorInfoId]}
        detail={visitorInfoId ? invitationDetails[visitorInfoId] : undefined}
        workflowRulesByCategory={workflowRulesByCategory}
        onClose={closeVisitorInfo}
      />
    </div>
  )
}
