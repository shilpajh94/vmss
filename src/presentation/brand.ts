import logoLight from '../assets/brand/logo-visimio.png'
import logoLight2x from '../assets/brand/logo-visimio@2x.png'
import logoOnDark from '../assets/brand/logo-visimio-on-dark.png'
import logoOnDark2x from '../assets/brand/logo-visimio-on-dark@2x.png'
import logoMark from '../assets/brand/logo-visimio-mark.png'
import logoMark2x from '../assets/brand/logo-visimio-mark@2x.png'
import { configuredEmail, configuredUrl } from './utils/configured-value'

// The one place the product's name and logo live (brand-identity
// capability). The PNGs are generated from the supplied logo by
// VMSS_API/scripts/build_brand_assets.py --web-out; regenerate rather than
// hand-edit. `public/firebase-messaging-sw.js` can't import this module and
// keeps its own copy of BRAND_NAME.
export const BRAND_NAME = 'Visimio'

// Per-deployment support address; the portal footer hides its support
// line when this is unset rather than showing a made-up address.
export const SUPPORT_EMAIL: string | null = configuredEmail(import.meta.env.VITE_SUPPORT_EMAIL)

// Per-deployment policy pages, linked from the portal and sign-in footers.
// Each link is hidden while its URL is unset, never pointed at `#`.
export const PRIVACY_POLICY_URL: string | null = configuredUrl(import.meta.env.VITE_PRIVACY_URL)
export const TERMS_URL: string | null = configuredUrl(import.meta.env.VITE_TERMS_URL)
export const SECURITY_POLICY_URL: string | null = configuredUrl(import.meta.env.VITE_SECURITY_URL)

export interface FooterLink {
  label: string
  href: string
}

// The footer links that have a URL configured, in display order.
export function footerLinks(links: Array<{ label: string; href: string | null }>): FooterLink[] {
  return links.filter((link): link is FooterLink => link.href !== null)
}

export const BRAND_LOGOS = {
  // Dark wordmark, for light surfaces.
  light: { src: logoLight, src2x: logoLight2x },
  // White wordmark, for the navy sidebars and staff headers.
  'on-dark': { src: logoOnDark, src2x: logoOnDark2x },
  // Follows the theme: dark wordmark in light, white wordmark in dark. For
  // surfaces that change with the theme.
  themed: { src: logoLight, src2x: logoLight2x, darkSrc: logoOnDark, darkSrc2x: logoOnDark2x },
  // The Visimio mark alone.
  mark: { src: logoMark, src2x: logoMark2x },
} as const

export type BrandLogoVariant = keyof typeof BRAND_LOGOS

export function copyrightLine(): string {
  return `© ${new Date().getFullYear()} ${BRAND_NAME}. All rights reserved.`
}
