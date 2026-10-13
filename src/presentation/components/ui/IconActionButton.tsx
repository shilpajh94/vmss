import type { ComponentType, SVGProps } from 'react'

interface IconActionButtonProps {
  icon: ComponentType<SVGProps<SVGSVGElement>>
  /** Action name, shown as the tooltip, e.g. "Edit". */
  label: string
  /** Screen-reader name, e.g. "Edit for INV-00003". */
  accessibleName: string
  onClick: () => void
}

// The tooltip is CSS-only and also shows on keyboard focus, which a plain
// `title` attribute would not. It is anchored to the button's left edge rather
// than centred so the first icon's tooltip isn't clipped by the column's scroll area.
export function IconActionButton({ icon: Icon, label, accessibleName, onClick }: IconActionButtonProps) {
  return (
    <button
      type="button"
      aria-label={accessibleName}
      onClick={onClick}
      className="group relative flex size-8 shrink-0 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-secondary-accent/8 hover:text-secondary-accent focus-visible:ring-2 focus-visible:ring-secondary-accent/40 focus-visible:outline-none active:bg-secondary-accent/15 max-lg:size-10"
    >
      <Icon className="size-4" />
      <span
        aria-hidden
        className="pointer-events-none absolute bottom-full left-0 z-20 mb-1 rounded-md bg-text px-2 py-1 font-body text-[11px] font-medium whitespace-nowrap text-surface opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
      >
        {label}
      </span>
    </button>
  )
}
