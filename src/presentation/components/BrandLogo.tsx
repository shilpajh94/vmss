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
  const { src } = BRAND_LOGOS[variant]
  // `max-w-fit` caps the used width at the image's natural width for its
  // height, so a stretching flex/grid parent can't widen (and distort) it;
  // `object-contain` keeps the ratio even if a layout forces a box anyway.
  return (
    <img
      src={src}
      alt={decorative ? '' : BRAND_NAME}
      className={`block w-auto max-w-fit shrink-0 object-contain object-left ${className}`}
    />
  )
}
