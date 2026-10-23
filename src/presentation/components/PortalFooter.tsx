import { PRIVACY_POLICY_URL, SUPPORT_EMAIL, TERMS_URL, copyrightLine, footerLinks } from '../brand'
import { BrandLogo } from './BrandLogo'

const LINKS = footerLinks([
  { label: 'Privacy Policy', href: PRIVACY_POLICY_URL },
  { label: 'Terms of Service', href: TERMS_URL },
])

export function PortalFooter() {
  return (
    <footer className="w-full border-t border-border bg-surface px-4 py-4 md:px-12 lg:py-5">
      <div className="flex w-full flex-col gap-3 lg:flex-row lg:items-center lg:justify-between lg:gap-6">
        {/* One row from lg up, so the footer stays slim (responsive-layout
            "The Public Portal Footer Is Compact"). */}
        <div className="flex min-w-0 flex-col gap-1 lg:flex-row lg:items-center lg:gap-4">
          <BrandLogo variant="themed" className="h-7 self-start lg:self-center" />
          <p className="font-body text-[13px] text-text-muted">Secure corporate guest registry and access automation.</p>
          <p className="font-body text-[12px] text-text-faint">{copyrightLine()}</p>
        </div>
        <div className="flex flex-col items-start gap-3 font-body text-[13px] text-text-muted sm:flex-row sm:flex-wrap sm:gap-6 lg:whitespace-nowrap">
          {LINKS.map((link) => (
            <a key={link.label} href={link.href} className="inline-flex min-h-10 items-center hover:text-text lg:min-h-0">
              {link.label}
            </a>
          ))}
          {SUPPORT_EMAIL && (
            <a href={`mailto:${SUPPORT_EMAIL}`} className="inline-flex min-h-10 items-center break-all hover:text-text lg:min-h-0">
              Support Contact: {SUPPORT_EMAIL}
            </a>
          )}
        </div>
      </div>
    </footer>
  )
}
