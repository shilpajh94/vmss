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

export function ActionCard({ icon, title, description, to, buttonLabel, variant }: ActionCardProps): ReactNode {
  return (
    <div className="flex w-full max-w-[480px] flex-col gap-6 rounded-2xl border border-border bg-surface p-5 md:p-8 shadow-[0_4px_8px_rgba(15,23,42,0.03)]">
      <div className="flex size-14 items-center justify-center rounded-xl bg-secondary-accent-soft">
        <img src={icon} alt="" className="size-7" />
      </div>
      <div className="flex flex-col gap-2">
        <p className="font-display text-[22px] font-bold text-text">{title}</p>
        <p className="text-body text-text-muted">{description}</p>
      </div>
      <Link
        to={to}
        className={
          variant === "filled"
            ? "flex w-full items-center justify-center rounded-lg bg-primary px-6 py-3 font-body text-[14px] font-semibold text-white"
            : "flex w-full items-center justify-center rounded-lg border border-primary px-6 py-3 font-body text-[14px] font-semibold text-primary"
        }
      >
        {buttonLabel}
      </Link>
    </div>
  )
}
