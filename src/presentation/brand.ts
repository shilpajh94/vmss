import logoLight from '../assets/brand/logo-visimio.png'
import logoLight2x from '../assets/brand/logo-visimio@2x.png'
import logoOnDark from '../assets/brand/logo-visimio-on-dark.png'
import logoOnDark2x from '../assets/brand/logo-visimio-on-dark@2x.png'
import logoMark from '../assets/brand/logo-visimio-mark.png'
import logoMark2x from '../assets/brand/logo-visimio-mark@2x.png'

// The one place the product's name and logo live (brand-identity
// capability). The PNGs are generated from the supplied logo by
// VMSS_API/scripts/build_brand_assets.py --web-out; regenerate rather than
// hand-edit. `public/firebase-messaging-sw.js` can't import this module and
// keeps its own copy of BRAND_NAME.
export const BRAND_NAME = 'Visimio'

export const BRAND_LOGOS = {
  // Dark wordmark, for light surfaces.
  light: { src: logoLight, src2x: logoLight2x },
  // White wordmark, for the navy sidebars and staff headers.
  'on-dark': { src: logoOnDark, src2x: logoOnDark2x },
  // The "V" mark alone.
  mark: { src: logoMark, src2x: logoMark2x },
} as const

export type BrandLogoVariant = keyof typeof BRAND_LOGOS

export function copyrightLine(): string {
  return `© ${new Date().getFullYear()} ${BRAND_NAME}. All rights reserved.`
}
