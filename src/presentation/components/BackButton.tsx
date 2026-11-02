import { ChevronLeftIcon } from './icons'

interface BackButtonProps {
  onClick: () => void
  className?: string
}

// Shared back-navigation control for pages reached by navigating from
// another in-app page (e.g. a list page's "Add"/"Edit" action) rather than
// directly from the sidebar. Takes an explicit handler that navigates to the
// page's known parent route, not raw history navigation (`navigate(-1)`),
// since that breaks on a direct link/refresh with no history entry.
export function BackButton({ onClick, className }: BackButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Back"
      // 40px below `lg`, where it is tapped (responsive-layout touch targets).
      className={className ?? 'flex size-10 shrink-0 items-center justify-center rounded-full border border-border bg-surface lg:size-9'}
    >
      <ChevronLeftIcon className="size-4" />
    </button>
  )
}
