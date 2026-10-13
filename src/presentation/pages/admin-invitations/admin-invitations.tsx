import { useState } from 'react'
import { KanbanColumn } from '../../components/invitation-board/KanbanColumn'
import { ResponsiveBoard } from '../../components/invitation-board/ResponsiveBoard'
import { ApproveInvitationModal } from '../../components/invitation-board/ApproveInvitationModal'
import { DenyInvitationModal } from '../../components/invitation-board/DenyInvitationModal'
import { CheckOutVisitorModal } from '../../components/invitation-board/CheckOutVisitorModal'
import { RescheduleInvitationModal } from '../../components/invitation-board/RescheduleInvitationModal'
import { DelegateInvitationModal } from '../../components/invitation-board/DelegateInvitationModal'
import { EditInvitationModal } from '../../components/invitation-board/EditInvitationModal'
import { VisitorInfoModal } from '../../components/invitation-board/VisitorInfoModal'
import { LoadingState } from '../../components/ui/LoadingState'
import { BoardFilterBar } from '../../components/invitation-board/BoardFilterBar'
import { CircleDotIcon, ClipboardListIcon } from '../../components/icons'
import { PageContentLayout } from '../../components/PageContentLayout'
import { usePageHeader } from '../../context/page-header-context'
import { useAdminInvitations } from './hooks/use-admin-invitations'

const STATUS_OPTIONS = [
  { value: 'submitted', label: 'Requested' },
  { value: 'approved', label: 'Approved' },
  { value: 'checked_in', label: 'Checked-in' },
  { value: 'checked_out', label: 'Checked-out' },
  { value: 'denied', label: 'Denied' },
]

const SOURCE_OPTIONS = [
  { value: 'staff_pre_registration', label: 'Staff Pre-Registration' },
  { value: 'visitor_walk_in', label: 'Visitor Walk-in' },
]

const STATUS_FILTER_OPTIONS = [{ value: '', label: 'All statuses' }, ...STATUS_OPTIONS]

const SOURCE_FILTER_OPTIONS = [{ value: '', label: 'All sources' }, ...SOURCE_OPTIONS]

const EMPTY_MESSAGES: Record<string, string> = {
  requested: 'No requested visits',
  approved: 'No approved visits',
  checked_in: 'No checked-in visitors today',
  checked_out: 'No checked-out visits',
  denied: 'No denied visits',
}

export function AdminInvitationsPage() {
  const [pendingApproveId, setPendingApproveId] = useState<string | undefined>(undefined)
  const {
    columns,
    isLoading,
    errorMessage,
    search,
    setSearch,
    purposeFilter,
    setPurposeFilter,
    purposeOptions,
    statusFilter,
    setStatusFilter,
    registrationTypeFilter,
    setRegistrationTypeFilter,
    sourceFilter,
    setSourceFilter,
    refresh,
    approve,
    approvingId,
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

  const isFiltering = purposeFilter !== 'all' || statusFilter !== '' || registrationTypeFilter !== 'all' || sourceFilter !== ''
  // Leaves the search text alone - only the dropdown filters reset.
  const clearFilters = () => {
    setPurposeFilter('all')
    setStatusFilter('')
    setRegistrationTypeFilter('all')
    setSourceFilter('')
  }

  return (
    <PageContentLayout
      header={
        <>
          <h1 className="font-display text-xl font-bold md:text-2xl text-text">Invitations</h1>
          <BoardFilterBar
            search={search}
            onSearchChange={setSearch}
            searchPlaceholder="Search visitor, tracking ID..."
            purposeFilter={purposeFilter}
            onPurposeFilterChange={setPurposeFilter}
            purposeOptions={purposeOptions}
            registrationTypeFilter={registrationTypeFilter}
            onRegistrationTypeFilterChange={setRegistrationTypeFilter}
            extraFilters={[
              { icon: CircleDotIcon, value: statusFilter, options: STATUS_FILTER_OPTIONS, onChange: setStatusFilter, ariaLabel: 'Status' },
              { icon: ClipboardListIcon, value: sourceFilter, options: SOURCE_FILTER_OPTIONS, onChange: setSourceFilter, ariaLabel: 'Source' },
            ]}
            isFiltering={isFiltering}
            onClearFilters={clearFilters}
          />

        </>
      }
    >
      {errorMessage ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-6 text-center md:p-12">
          <p className="font-body text-sm text-danger">{errorMessage}</p>
          <button type="button" onClick={refresh} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
            Try again
          </button>
        </div>
      ) : isLoading ? (
        <LoadingState label="Loading invitations…" className="flex-1" />
      ) : (
        // PageContentLayout's data region has a definite height on desktop;
        // filling it lets each column scroll under its own fixed header.
        <div className="flex flex-col lg:h-full">
          <ResponsiveBoard
            columns={columns}
            renderColumn={(column) => (
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
                onMoveToApproved={column.status === 'requested' ? setPendingApproveId : undefined}
                onMoveToDenied={column.status === 'requested' ? requestDeny : undefined}
                approvingId={approvingId}
                invitationDetails={invitationDetails}
                roleNameById={roleNameById}
                employeeNameById={employeeNameById}
                workflowRulesByCategory={workflowRulesByCategory}
                onRescheduleClick={requestReschedule}
                onDelegateClick={requestDelegate}
                onApproveAndDelegateClick={requestApproveAndDelegate}
                onApproveClick={setPendingApproveId}
                onEditClick={requestEdit}
                onVisitorInfoClick={viewVisitorInfo}
                onCheckOutClick={column.status === 'checked_in' && canCheckOut ? requestCheckOut : undefined}
              />
            )}
          />
        </div>
      )}

      <ApproveInvitationModal
        isOpen={pendingApproveId !== undefined}
        isApproving={approvingId !== undefined}
        onCancel={() => setPendingApproveId(undefined)}
        onConfirm={() => {
          const id = pendingApproveId
          setPendingApproveId(undefined)
          if (id) void approve(id)
        }}
      />

      <DenyInvitationModal isOpen={pendingDenyId !== undefined} isDenying={denyingId !== undefined} onConfirm={confirmDeny} onCancel={cancelDeny} />

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
    </PageContentLayout>
  )
}
