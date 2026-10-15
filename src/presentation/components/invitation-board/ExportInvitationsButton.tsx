import { DownloadIcon } from '../icons'

interface ExportInvitationsButtonProps {
  onClick: () => void
  /** Icon-only below `md` (accessible name kept), for the crowded staff header. */
  compact?: boolean
}

// Same 40px height as the board's filter controls, so it sits flush beside them.
export function ExportInvitationsButton({ onClick, compact = false }: ExportInvitationsButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={compact ? 'Export' : undefined}
      className={`flex h-10 shrink-0 items-center justify-center gap-2 rounded-lg border border-border bg-surface font-body text-[13px] font-semibold text-text hover:bg-bg ${
        compact ? 'min-w-10 px-2.5 md:px-3' : 'px-3'
      }`}
    >
      <DownloadIcon className="size-4 text-text-muted" />
      <span className={compact ? 'hidden md:inline' : undefined}>Export</span>
    </button>
  )
}
