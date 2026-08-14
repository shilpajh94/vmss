interface SummaryStatCardProps {
  label: string
  value: number
}

export function SummaryStatCard({ label, value }: SummaryStatCardProps) {
  return (
    <div className="flex flex-1 flex-col gap-2 rounded-xl border border-border bg-surface p-4 drop-shadow-[0px_2px_5px_rgba(0,0,0,0.04)]">
      <p className="font-body text-xs font-semibold text-text-muted">{label}</p>
      <p className="font-display text-2xl font-bold text-text">{value.toLocaleString()}</p>
    </div>
  )
}
