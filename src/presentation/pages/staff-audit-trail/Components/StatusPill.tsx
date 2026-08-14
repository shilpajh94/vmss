interface StatusPillProps {
  status: string
}

const STATUS_STYLES: Record<string, { bg: string; text: string }> = {
  Approved: { bg: 'bg-success/10', text: 'text-success' },
  Completed: { bg: 'bg-neutral-subtle', text: 'text-text-muted' },
  Rejected: { bg: 'bg-danger/10', text: 'text-danger' },
  Flagged: { bg: 'bg-danger/10', text: 'text-danger' },
  Modified: { bg: 'bg-modified/10', text: 'text-modified' },
}

const DEFAULT_STATUS_STYLE = { bg: 'bg-neutral-subtle', text: 'text-text-muted' }

export function StatusPill({ status }: StatusPillProps) {
  const style = STATUS_STYLES[status] ?? DEFAULT_STATUS_STYLE

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 font-body text-xs font-bold whitespace-nowrap ${style.bg} ${style.text}`}>
      {status}
    </span>
  )
}
