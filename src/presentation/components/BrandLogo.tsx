import { BRAND_LOGOS, BRAND_NAME, type BrandLogoVariant } from '../brand'

interface BrandLogoProps {
  variant: BrandLogoVariant
  // Height (and any other sizing); width follows the logo's aspect ratio.
  className?: string
  // Empty alt when the logo sits next to visible BRAND_NAME text or inside a
  // link that already carries the accessible name.
  decorative?: boolean
}

export function BrandLogo({ variant, className = 'h-8', decorative = false }: BrandLogoProps) {
  const logo = BRAND_LOGOS[variant]
  const alt = decorative ? '' : BRAND_NAME
  // `max-w-fit` caps the used width at the image's natural width for its
  // height, so a stretching flex/grid parent can't widen (and distort) it;
  // `object-contain` keeps the ratio even if a layout forces a box anyway.
  const sizing = `w-auto max-w-fit shrink-0 object-contain object-left ${className}`
  if ('darkSrc' in logo) {
    // Both lockups are in the markup and CSS shows one, so a live theme
    // switch (or no provider at all) needs no re-render; the hidden one is
    // `display: none`, so only one alt is announced.
    return (
      <>
        <img src={logo.src} srcSet={`${logo.src} 1x, ${logo.src2x} 2x`} alt={alt} className={`block dark:hidden ${sizing}`} />
        <img src={logo.darkSrc} srcSet={`${logo.darkSrc} 1x, ${logo.darkSrc2x} 2x`} alt={alt} className={`hidden dark:block ${sizing}`} />
      </>
    )
  }
  return <img src={logo.src} srcSet={`${logo.src} 1x, ${logo.src2x} 2x`} alt={alt} className={`block ${sizing}`} />
}
