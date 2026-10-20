import { Link } from 'react-router'
import { BRAND_NAME } from '../brand'
import { BrandLogo } from './BrandLogo'

interface PortalHeaderProps {
  backTo?: string
}

export function PortalHeader({ backTo }: PortalHeaderProps) {
  return (
    <header className="flex h-16 w-full items-center gap-3 border-b border-border bg-surface px-4 md:h-[72px] md:px-12">
      {backTo && (
        <Link
          to={backTo}
          aria-label="Back"
          className="flex size-10 items-center justify-center rounded-full border border-border text-text lg:size-9"
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
      <Link to="/" aria-label={`${BRAND_NAME} home`} className="flex items-center">
        <BrandLogo variant="light" className="h-7 md:h-8" decorative />
      </Link>
    </header>
  )
}
