import { PRIVACY_POLICY_URL, SUPPORT_EMAIL, TERMS_URL, footerLinks, type FooterLink } from '../../brand'
import type { BrandCopy } from './SplitScreenLayout'

// The brand panel and footer every visitor screen shares, so the panel reads
// the same from the landing page through the request, track and error pages
// (public-page-layout "Visitor screens share one brand copy and footer").
export const VISITOR_BRAND: BrandCopy = {
  headline: (
    <>
      Welcome to the Visitor <span className="text-secondary-accent">Portal.</span>
    </>
  ),
  tagline: 'Request a secure entry pass or keep track of your active registrations in real-time.',
  highlights: [
    {
      label: 'Pre-register before you arrive',
      icon: 'M8 7V3m8 4V3M4 11h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Zm4 10 2 2 4-4',
    },
    {
      label: 'A QR pass for quick check-in',
      icon: 'M4 4h6v6H4V4Zm10 0h6v6h-6V4ZM4 14h6v6H4v-6Zm10 0h2v2h-2v-2Zm4 0h2v2h-2v-2Zm-4 4h2v2h-2v-2Zm4 4v-2',
    },
    {
      label: 'Track your request status live',
      icon: 'm21 21-4.35-4.35M19 11a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z',
    },
  ],
}

export function visitorFooterLinks(): FooterLink[] {
  return [
    ...footerLinks([
      { label: 'Privacy Policy', href: PRIVACY_POLICY_URL },
      { label: 'Terms of Service', href: TERMS_URL },
    ]),
    ...(SUPPORT_EMAIL ? [{ label: `Support Contact: ${SUPPORT_EMAIL}`, href: `mailto:${SUPPORT_EMAIL}` }] : []),
  ]
}
