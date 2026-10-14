import { DownloadIcon } from '../icons'

// Same 40px height as the board's filter controls, so it sits flush beside them.
export function ExportInvitationsButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex h-10 shrink-0 items-center justify-center gap-2 rounded-lg border border-border bg-surface px-3 font-body text-[13px] font-semibold text-text hover:bg-bg"
    >
      <DownloadIcon className="size-4 text-text-muted" />
      Export
    </button>
  )
}
