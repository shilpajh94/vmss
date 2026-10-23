interface StatusBadgeProps {
  isActive: boolean
  activeLabel?: string
  inactiveLabel?: string
}

// The Active/Inactive pill every admin register shows. The inactive text is
// `text-secondary`: `text-muted` on the `border-subtle` fill was 4.3:1,
// short of WCAG AA (design D-W11).
export function StatusBadge({ isActive, activeLabel = 'Active', inactiveLabel = 'Inactive' }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-body text-xs font-semibold ${
        isActive ? 'bg-success/15 text-success-text' : 'bg-border-subtle text-text-secondary'
      }`}
    >
      <span aria-hidden className={`size-1.5 rounded-full ${isActive ? 'bg-success' : 'bg-text-faint'}`} />
      {isActive ? activeLabel : inactiveLabel}
    </span>
  )
}
