import logoLight from '../assets/brand/logo-guestify.svg'
import logoOnDark from '../assets/brand/logo-guestify-on-dark.svg'
import logoMark from '../assets/brand/logo-guestify-mark.svg'

// The one place the product's name and logo live (brand-identity
// capability). The SVGs are generated from the master logo in
// VMSS_API/brand/ by VMSS_API/scripts/build_brand_assets.py --web-out;
// regenerate rather than hand-edit. `public/firebase-messaging-sw.js` can't import this module and
// keeps its own copy of BRAND_NAME.
export const BRAND_NAME = 'Guestify'

// Per-deployment support address; the portal footer hides its support
// line when this is unset rather than showing a made-up address.
export const SUPPORT_EMAIL: string | null = import.meta.env.VITE_SUPPORT_EMAIL?.trim() || null

export const BRAND_LOGOS = {
  // Dark wordmark, for light surfaces.
  light: { src: logoLight },
  // White wordmark, for the navy sidebars and staff headers.
  'on-dark': { src: logoOnDark },
  // The "G" pin mark alone.
  mark: { src: logoMark },
} as const

export type BrandLogoVariant = keyof typeof BRAND_LOGOS

export function copyrightLine(): string {
  return `© ${new Date().getFullYear()} ${BRAND_NAME}. All rights reserved.`
}
