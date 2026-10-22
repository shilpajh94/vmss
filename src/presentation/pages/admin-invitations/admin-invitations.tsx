import { KanbanColumn } from '../../components/invitation-board/KanbanColumn'
import { ResponsiveBoard } from '../../components/invitation-board/ResponsiveBoard'
import { CLOSED_BOARD_STATUSES } from '../../hooks/use-invitations-board'
import { ApproveInvitationModal } from '../../components/invitation-board/ApproveInvitationModal'
import { DenyInvitationModal } from '../../components/invitation-board/DenyInvitationModal'
import { RevertApprovalModal } from '../../components/invitation-board/RevertApprovalModal'
import { CheckOutVisitorModal } from '../../components/invitation-board/CheckOutVisitorModal'
import { RescheduleInvitationModal } from '../../components/invitation-board/RescheduleInvitationModal'
import { DelegateInvitationModal } from '../../components/invitation-board/DelegateInvitationModal'
import { EditInvitationModal } from '../../components/invitation-board/EditInvitationModal'
import { VisitorInfoModal } from '../../components/invitation-board/VisitorInfoModal'
import { AsyncRegion } from '../../components/AsyncRegion'
import { BoardSkeleton } from '../../components/ui/Skeleton'
import { BoardFilterBar } from '../../components/invitation-board/BoardFilterBar'
import { boardExtraFilters } from '../../components/invitation-board/board-extra-filters'
import { ExportInvitationsButton } from '../../components/invitation-board/ExportInvitationsButton'
import { ExportInvitationsModal } from '../../components/invitation-board/ExportInvitationsModal'
import { PageContentLayout } from '../../components/PageContentLayout'
import { usePageHeader } from '../../context/page-header-context'
import { useAdminInvitations } from './hooks/use-admin-invitations'

const EMPTY_MESSAGES: Record<string, string> = {
  requested: 'No requested visits',
  approved: 'No approved visits',
  checked_in: 'No checked-in visitors today',
  checked_out: 'No checked-out visits',
  denied: 'No denied visits',
  archived: 'No archived visits',
}

export function AdminInvitationsPage() {
  const {
    columns,
    phase,
    isRefreshing,
    search,
    setSearch,
    purposeFilter,
    setPurposeFilter,
    purposeOptions,
    statusFilter,
    focusClosedStatus,
    setStatusFilter,
    registrationTypeFilter,
    setRegistrationTypeFilter,
    sourceFilter,
    setSourceFilter,
    isFiltering,
    clearFilters,
    refresh,
    approvingId,
    findRequest,
    pendingApproveId,
    requestApprove,
    cancelApprove,
    confirmApprove,
    pendingRevertId,
    requestRevert,
    cancelRevert,
    confirmRevert,
    revertingId,
    invitationDetails,
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
    canCheckOut,
    canExport,
    actionPermissions,
    isExportOpen,
    openExport,
    closeExport,
    exportInvitations,
    isExporting,
    exportError,
    exportFilterSummary,
    pendingCheckOutId,
    pendingCheckOutRequest,
    requestCheckOut,
    cancelCheckOut,
    confirmCheckOut,
    checkingOutId,
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
  } = useAdminInvitations()

  usePageHeader({ description: 'Monitor visitor invitations, approval status, and check-in progress' })

  return (
    <PageContentLayout
      header={
        <>
          {/* In the title row, not the filter bar: the bar's search + four
              dropdowns already need the full row on wide screens. */}
          <div className="flex items-center justify-between gap-3">
            <h1 className="font-display text-xl font-bold md:text-2xl text-text">Invitations</h1>
            {canExport ? <ExportInvitationsButton onClick={openExport} /> : null}
          </div>
          <BoardFilterBar
            search={search}
            onSearchChange={setSearch}
            searchPlaceholder="Search visitor, tracking ID..."
            purposeFilter={purposeFilter}
            onPurposeFilterChange={setPurposeFilter}
            purposeOptions={purposeOptions}
            registrationTypeFilter={registrationTypeFilter}
            onRegistrationTypeFilterChange={setRegistrationTypeFilter}
            extraFilters={boardExtraFilters({ statusFilter, setStatusFilter, sourceFilter, setSourceFilter })}
            isFiltering={isFiltering}
            onClearFilters={clearFilters}
          />

        </>
      }
    >
      <AsyncRegion
        phase={phase}
        isRefreshing={isRefreshing}
        skeleton={<BoardSkeleton />}
        errorMessage="Something went wrong loading the dashboard. Please try again."
        onRetry={refresh}
        className="lg:h-full"
      >
        {/* PageContentLayout's data region has a definite height on desktop;
            filling it lets each column scroll under its own fixed header. */}
        <div className="flex flex-col lg:h-full">
          <ResponsiveBoard
            boardKey="admin"
            columns={columns}
            closedStatuses={CLOSED_BOARD_STATUSES}
            focusClosedStatus={focusClosedStatus}
            renderColumn={(column, { embedded }) => (
              <KanbanColumn
                key={`${column.status}:${column.resetKey}`}
                status={column.status}
                label={column.label}
                requests={column.requests}
                total={column.total}
                hasMore={column.hasMore}
                isLoadingMore={column.isLoadingMore}
                loadMoreFailed={column.loadMoreFailed}
                onLoadMore={column.loadMore}
                emptyMessage={EMPTY_MESSAGES[column.status]}
                embedded={embedded}
                onDrop={
                  column.status === 'approved' && actionPermissions.approve
                    ? requestApprove
                    : column.status === 'denied' && actionPermissions.deny
                      ? requestDeny
                      : undefined
                }
                onMoveToApproved={column.status === 'requested' && actionPermissions.approve ? requestApprove : undefined}
                onMoveToDenied={column.status === 'requested' && actionPermissions.deny ? requestDeny : undefined}
                approvingId={approvingId}
                invitationDetails={invitationDetails}
                roleNameById={roleNameById}
                employeeNameById={employeeNameById}
                workflowRulesByCategory={workflowRulesByCategory}
                onRescheduleClick={actionPermissions.reschedule ? requestReschedule : undefined}
                onDelegateClick={actionPermissions.delegate ? requestDelegate : undefined}
                onApproveAndDelegateClick={actionPermissions.approve ? requestApproveAndDelegate : undefined}
                onApproveClick={actionPermissions.approve ? requestApprove : undefined}
                onEditClick={actionPermissions.edit ? requestEdit : undefined}
                onVisitorInfoClick={viewVisitorInfo}
                onCheckOutClick={column.status === 'checked_in' && canCheckOut ? requestCheckOut : undefined}
                onRevertClick={column.status === 'approved' && actionPermissions.revert ? requestRevert : undefined}
              />
            )}
          />
        </div>
      </AsyncRegion>

      <ApproveInvitationModal
        isOpen={pendingApproveId !== undefined}
        visitorName={findRequest(pendingApproveId)?.primaryContactFullName}
        trackingId={findRequest(pendingApproveId)?.trackingId}
        isApproving={approvingId !== undefined}
        onConfirm={() => void confirmApprove()}
        onCancel={cancelApprove}
      />

      <RevertApprovalModal
        isOpen={pendingRevertId !== undefined}
        visitorName={findRequest(pendingRevertId)?.primaryContactFullName}
        trackingId={findRequest(pendingRevertId)?.trackingId}
        isReverting={revertingId !== undefined}
        onConfirm={confirmRevert}
        onCancel={cancelRevert}
      />

      <DenyInvitationModal
        isOpen={pendingDenyId !== undefined}
        visitorName={findRequest(pendingDenyId)?.primaryContactFullName}
        trackingId={findRequest(pendingDenyId)?.trackingId}
        isDenying={denyingId !== undefined}
        onConfirm={confirmDeny}
        onCancel={cancelDeny}
      />

      <CheckOutVisitorModal
        isOpen={pendingCheckOutId !== undefined}
        visitorName={pendingCheckOutRequest?.primaryContactFullName}
        trackingId={pendingCheckOutRequest?.trackingId}
        isCheckingOut={checkingOutId !== undefined}
        onConfirm={() => void confirmCheckOut()}
        onCancel={cancelCheckOut}
      />

      <RescheduleInvitationModal
        isOpen={pendingRescheduleId !== undefined}
        visitorName={findRequest(pendingRescheduleId)?.primaryContactFullName}
        trackingId={findRequest(pendingRescheduleId)?.trackingId}
        isRescheduling={reschedulingId !== undefined}
        onConfirm={(preferredVisitDate, preferredVisitTime) =>
          pendingRescheduleId && reschedule(pendingRescheduleId, preferredVisitDate, preferredVisitTime)
        }
        onCancel={cancelReschedule}
      />

      <DelegateInvitationModal
        isOpen={pendingDelegateId !== undefined}
        visitorName={findRequest(pendingDelegateId)?.primaryContactFullName}
        trackingId={findRequest(pendingDelegateId)?.trackingId}
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
        visitorName={findRequest(pendingApproveAndDelegateId)?.primaryContactFullName}
        trackingId={findRequest(pendingApproveAndDelegateId)?.trackingId}
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

      <ExportInvitationsModal
        isOpen={isExportOpen}
        initialStatus={statusFilter}
        appliedFilters={exportFilterSummary}
        isExporting={isExporting}
        errorMessage={exportError}
        onConfirm={(choice) => void exportInvitations(choice)}
        onClose={closeExport}
      />

      <VisitorInfoModal
        isOpen={visitorInfoId !== undefined}
        isLoading={visitorInfoId !== undefined && !invitationDetails[visitorInfoId]}
        detail={visitorInfoId ? invitationDetails[visitorInfoId] : undefined}
        workflowRulesByCategory={workflowRulesByCategory}
        employeeNameById={employeeNameById}
        onClose={closeVisitorInfo}
      />
    </PageContentLayout>
  )
}
