import { useState } from 'react'
import { KanbanColumn } from '../../components/invitation-board/KanbanColumn'
import { DenyInvitationModal } from '../../components/invitation-board/DenyInvitationModal'
import { RescheduleInvitationModal } from '../../components/invitation-board/RescheduleInvitationModal'
import { DelegateInvitationModal } from '../../components/invitation-board/DelegateInvitationModal'
import { EditInvitationModal } from '../../components/invitation-board/EditInvitationModal'
import { VisitorInfoModal } from '../../components/invitation-board/VisitorInfoModal'
import { LoadingState } from '../../components/ui/LoadingState'
import { SelectField } from '../../components/ui/SelectField'
import { SearchGlyphIcon, SlidersIcon } from '../../components/icons'
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

const REGISTRATION_TYPE_OPTIONS = [
  { value: 'all', label: 'All types' },
  { value: 'individual', label: 'Individual' },
  { value: 'group', label: 'Group' },
]

const SOURCE_OPTIONS = [
  { value: 'staff_pre_registration', label: 'Staff Pre-Registration' },
  { value: 'visitor_walk_in', label: 'Visitor Walk-in' },
]

const EMPTY_MESSAGES: Record<string, string> = {
  requested: 'No requested visits',
  approved: 'No approved visits',
  checked_in: 'No checked-in visitors today',
  denied: 'No denied visits',
}

export function AdminInvitationsPage() {
  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const {
    columns,
    isLoading,
    errorMessage,
    search,
    setSearch,
    statusFilter,
    setStatusFilter,
    registrationTypeFilter,
    setRegistrationTypeFilter,
    sourceFilter,
    setSourceFilter,
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
    visitorInfoId,
    viewVisitorInfo,
    closeVisitorInfo,
  } = useAdminInvitations()

  usePageHeader({ description: 'Monitor visitor invitations, approval status, and check-in progress' })

  const isFiltering = statusFilter !== '' || registrationTypeFilter !== 'all' || sourceFilter !== ''
  const clearFilters = () => {
    setStatusFilter('')
    setRegistrationTypeFilter('all')
    setSourceFilter('')
  }

  return (
    <PageContentLayout
      header={
        <>
          <div className="flex w-full items-center justify-between">
            <h1 className="font-display text-2xl font-bold text-text">Invitations</h1>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 rounded-full border border-border bg-surface p-btn-secondary">
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
                onClick={() => setIsFilterPanelOpen((current) => !current)}
                className="flex items-center gap-2 rounded-full border border-border bg-surface p-btn-secondary font-body text-[13px] font-semibold text-text"
              >
                <SlidersIcon className="size-3.5" />
                Filters
              </button>
            </div>
          </div>

          {isFilterPanelOpen && (
            <div className="flex w-full flex-wrap items-end gap-4 rounded-2xl border border-border bg-surface p-filter-panel">
              <div className="w-48">
                <SelectField label="Status" value={statusFilter} onChange={setStatusFilter} placeholder="All" options={STATUS_OPTIONS} />
              </div>
              <div className="w-48">
                <SelectField
                  label="Registration Type"
                  value={registrationTypeFilter}
                  onChange={setRegistrationTypeFilter}
                  options={REGISTRATION_TYPE_OPTIONS}
                />
              </div>
              <div className="w-48">
                <SelectField label="Source" value={sourceFilter} onChange={setSourceFilter} placeholder="All" options={SOURCE_OPTIONS} />
              </div>
              {isFiltering && (
                <button type="button" onClick={clearFilters} className="font-body text-[13px] font-semibold text-admin-accent">
                  Clear filters
                </button>
              )}
            </div>
          )}
        </>
      }
    >
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
        <div className="flex w-full flex-1 items-start gap-4 overflow-x-auto">
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
              onEditClick={requestEdit}
              onVisitorInfoClick={viewVisitorInfo}
            />
          ))}
        </div>
      )}

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
        onConfirm={(delegateUserId) => pendingDelegateId && delegate(pendingDelegateId, delegateUserId)}
        onCancel={cancelDelegate}
      />

      <EditInvitationModal
        isOpen={pendingEditId !== undefined}
        isSaving={editingId !== undefined}
        detail={pendingEditDetail}
        onConfirm={(fields) => pendingEditId && edit(pendingEditId, fields)}
        onCancel={cancelEdit}
      />

      <VisitorInfoModal
        isOpen={visitorInfoId !== undefined}
        isLoading={visitorInfoId !== undefined && !invitationDetails[visitorInfoId]}
        detail={visitorInfoId ? invitationDetails[visitorInfoId] : undefined}
        onClose={closeVisitorInfo}
      />
    </PageContentLayout>
  )
}
