import { copyrightLine } from '../brand'
import { BrandLogo } from './BrandLogo'

export function PortalFooter() {
  return (
    <footer className="w-full border-t border-border bg-surface px-4 py-8 md:px-12 md:py-10">
      <div className="flex w-full flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex w-full max-w-[400px] flex-col gap-1">
          <BrandLogo variant="light" className="h-7 self-start" />
          <p className="mt-1 font-body text-[13px] text-text-muted">Secure corporate guest registry and access automation.</p>
          <p className="font-body text-[12px] text-text-faint">{copyrightLine()}</p>
        </div>
        <div className="flex flex-col items-start gap-3 font-body text-[13px] text-text-muted sm:flex-row sm:flex-wrap sm:gap-6 lg:whitespace-nowrap">
          <a href="#" className="hover:text-text">
            Privacy Policy
          </a>
          <a href="#" className="hover:text-text">
            Terms of Service
          </a>
          <a href="mailto:support@visitorpass.co" className="hover:text-text">
            Support Contact: support@visitorpass.co
          </a>
        </div>
      </div>
    </footer>
  )
}
