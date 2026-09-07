import logoMark from '../../../../assets/logo-mark.svg'

export function StaffPortalHeader() {
  return (
    <header className="relative flex w-full items-center justify-between border-b border-[#1e293b] bg-primary px-12 py-5">
      <div className="flex items-center gap-3">
        <img src={logoMark} alt="" className="size-8" />
        <span className="font-display text-2xl font-extrabold text-white">VisitorPass</span>
        <span className="rounded-md border border-[#334155] bg-[#1e293b] px-2.5 py-1 font-body text-[11px] font-bold tracking-[1px] text-secondary-accent">
          STAFF GATEWAY
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="relative flex size-2">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-success opacity-75" />
          <span className="relative inline-flex size-2 rounded-full bg-success" />
        </span>
        <span className="font-body text-[13px] font-semibold text-text-faint">All Systems Operational</span>
      </div>
    </header>
  )
}
