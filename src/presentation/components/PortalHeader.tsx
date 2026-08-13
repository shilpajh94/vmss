import { Link } from 'react-router'

interface PortalHeaderProps {
  backTo?: string
}

export function PortalHeader({ backTo }: PortalHeaderProps) {
  return (
    <header className="flex h-[72px] w-full items-center gap-3 border-b border-border bg-surface px-12">
      {backTo && (
        <Link
          to={backTo}
          aria-label="Back"
          className="flex size-9 items-center justify-center rounded-full border border-border text-text"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              d="M10 3L5 8L10 13"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </Link>
      )}
      <div className="flex items-center gap-2">
        <div className="flex size-8 items-center justify-center rounded-lg bg-primary">
          <span className="font-display text-[18px] font-extrabold text-white">V</span>
        </div>
        <span className="font-display text-[18px] font-extrabold text-text">VisitorPass</span>
      </div>
    </header>
  )
}
