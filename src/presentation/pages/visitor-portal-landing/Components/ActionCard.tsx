import type { ReactNode } from "react"
import { Link } from "react-router"

interface ActionCardProps {
  icon: string
  title: string
  description: string
  to: string
  buttonLabel: string
  variant: "filled" | "outlined"
}

// The whole card is one link, so a click anywhere on it navigates; its
// accessible name carries both the title and the call-to-action label.
export function ActionCard({ icon, title, description, to, buttonLabel, variant }: ActionCardProps): ReactNode {
  const primary = variant === "filled"

  return (
    <Link
      to={to}
      className={`group flex w-full flex-col gap-4 rounded-2xl border p-5 transition-[transform,box-shadow,border-color] duration-[var(--motion-fast)] hover:-translate-y-px focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary-accent md:p-6 xshort:gap-3 xshort:p-4 ${
        primary
          ? "border-secondary-accent/40 bg-secondary-accent-soft shadow-[0_8px_24px_-12px_rgba(6,182,212,0.45)] hover:shadow-[0_14px_28px_-12px_rgba(6,182,212,0.55)]"
          : "border-border bg-surface shadow-[0_4px_12px_-6px_rgba(15,23,42,0.08)] hover:border-border-strong hover:shadow-[0_12px_24px_-12px_rgba(15,23,42,0.18)]"
      }`}
    >
      <div className="flex items-start gap-4">
        <span
          className={`flex size-12 shrink-0 items-center justify-center rounded-xl ${primary ? "bg-secondary-accent" : "bg-secondary-accent-soft"}`}
        >
          {/* The icon SVGs are drawn in cyan; on the solid cyan tile they go white. */}
          <img src={icon} alt="" className={`size-6 ${primary ? "brightness-0 invert" : ""}`} />
        </span>
        <span className="flex flex-col gap-1">
          <span className="font-display text-[20px] font-bold text-text">{title}</span>
          <span className="text-body text-text-muted">{description}</span>
        </span>
      </div>
      <span
        className={`flex items-center justify-center gap-2 rounded-lg px-5 py-3 font-body text-[14px] font-semibold ${
          primary ? "bg-secondary-accent text-white" : "border border-border-strong text-text"
        }`}
      >
        {buttonLabel}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden className="transition-transform duration-[var(--motion-fast)] group-hover:translate-x-0.5">
          <path d="M5 12h14m-6-6 6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    </Link>
  )
}
