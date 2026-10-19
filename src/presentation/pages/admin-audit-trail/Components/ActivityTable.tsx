import type { AuditLogEntry } from '../../../../domain/entities/audit-log-entry-schema'

interface ActivityTableProps {
  entries: AuditLogEntry[]
  employeeNameById: Record<string, string>
}

const COLUMN_LABELS = ['Timestamp', 'Action', 'Actor', 'Entity Type']

// Curated labels for the actions surfaced in the activity-type filter, plus a
// few other common ones seen in real data — anything else falls back to a
// generic snake_case -> Title Case conversion so unrecognized actions still
// render legibly.
const ACTION_LABELS: Record<string, string> = {
  invitation_created: 'Invitation Created',
  walk_in_registration_created: 'Walk-in Registered',
  invitation_approved: 'Invitation Approved',
  invitation_approval_step_approved: 'Approval Step Approved',
  invitation_checked_in_public: 'Checked In',
  invitation_rescheduled: 'Rescheduled',
  login: 'Staff Login',
  branch_role_assigned: 'Role Assigned',
  employee_directory_synced: 'Employee Directory Synced',
  role_permissions_resynced: 'Permissions Resynced',
}

function humanizeAction(action: string): string {
  return (
    ACTION_LABELS[action] ??
    action
      .split('_')
      .map((word) => (word.length > 0 ? word[0].toUpperCase() + word.slice(1) : word))
      .join(' ')
  )
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export function ActivityTable({ entries, employeeNameById }: ActivityTableProps) {
  // The empty state is rendered by the page's AsyncRegion.
  return (
    <div className="flex w-full flex-1 flex-col overflow-x-auto rounded-xl border border-border bg-surface">
      <div className="flex w-full min-w-[480px] items-center gap-3 border-b border-border bg-border-subtle px-4 py-3 md:min-w-0">
        <p className="w-[120px] shrink-0 md:w-[160px] font-body text-xs font-bold text-text-muted">{COLUMN_LABELS[0]}</p>
        <p className="w-[150px] shrink-0 md:w-[200px] font-body text-xs font-bold text-text-muted">{COLUMN_LABELS[1]}</p>
        <p className="min-w-0 flex-1 font-body text-xs font-bold text-text-muted">{COLUMN_LABELS[2]}</p>
        <p className="hidden w-[140px] shrink-0 font-body text-xs font-bold text-text-muted md:block">{COLUMN_LABELS[3]}</p>
      </div>

      {entries.map((entry, index) => (
        <div
          key={entry.id}
          className={`flex w-full min-w-[480px] items-center gap-3 px-4 py-3 md:min-w-0 ${index < entries.length - 1 ? 'border-b border-border' : ''}`}
        >
          <p className="w-[120px] shrink-0 md:w-[160px] font-body text-[13px] text-text">{formatTimestamp(entry.createdAt)}</p>
          <p className="w-[150px] shrink-0 md:w-[200px] font-body text-[13px] font-semibold text-text">{humanizeAction(entry.action)}</p>
          <p className="min-w-0 flex-1 truncate font-body text-[13px] text-text-muted">
            {entry.actorUserId ? (employeeNameById[entry.actorUserId] ?? 'Unknown') : 'System'}
          </p>
          <p className="hidden w-[140px] shrink-0 font-body text-[13px] text-text md:block">{entry.entityType}</p>
        </div>
      ))}
    </div>
  )
}
