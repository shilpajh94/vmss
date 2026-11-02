import type { ReactNode } from 'react'
import { SplitScreenLayout, type BrandCopy } from '../layout/SplitScreenLayout'
import { SECURITY_POLICY_URL, SUPPORT_EMAIL, TERMS_URL, footerLinks } from '../../brand'

const LINKS = footerLinks([
  { label: 'Security Policy', href: SECURITY_POLICY_URL },
  { label: 'Terms of Service', href: TERMS_URL },
])

const BRAND: BrandCopy = {
  headline: (
    <>
      Every visitor, welcomed <span className="text-secondary-accent">securely.</span>
    </>
  ),
  tagline: 'Invitations, approvals, check-in and live occupancy for every branch, in one place.',
  highlights: [
    {
      label: 'Pre-registration and invitations',
      icon: 'M8 7V3m8 4V3M4 11h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Zm4 10 2 2 4-4',
    },
    {
      label: 'Fast QR check-in at the front desk',
      icon: 'M4 4h6v6H4V4Zm10 0h6v6h-6V4ZM4 14h6v6H4v-6Zm10 0h2v2h-2v-2Zm4 0h2v2h-2v-2Zm-4 4h2v2h-2v-2Zm4 4v-2',
    },
    {
      label: "Live view of who's inside, every branch",
      icon: 'M16 19v-1a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v1m14-16.87a4 4 0 0 1 0 7.75M22 19v-1a4 4 0 0 0-3-3.87M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z',
    },
  ],
}

const HELP_LINE = SUPPORT_EMAIL && (
  <p className="text-center font-body text-[13px] text-text-muted">
    Need help?{' '}
    <a href={`mailto:${SUPPORT_EMAIL}`} className="font-semibold text-secondary-accent underline-offset-2 hover:underline">
      Contact System Administrator
    </a>
  </p>
)

interface AuthSplitLayoutProps {
  portalLabel: string
  children: ReactNode
}

// The admin and staff sign-in pages' brand copy, links and help line on the
// shared split-screen shell.
export function AuthSplitLayout({ portalLabel, children }: AuthSplitLayoutProps) {
  return (
    <SplitScreenLayout portalLabel={portalLabel} brand={BRAND} footerLinks={LINKS} aside={HELP_LINE}>
      {children}
    </SplitScreenLayout>
  )
}
