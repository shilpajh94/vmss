import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { BrandLogo } from '../BrandLogo'
import { HeroImage } from '../HeroImage'
import { useIsDesktop } from '../../hooks/use-media-query'
import { copyrightLine, type FooterLink } from '../../brand'

export interface BrandHighlight {
  label: string
  // A 24×24 stroke path, drawn in the accent colour.
  icon: string
}

export interface BrandCopy {
  headline: ReactNode
  tagline: string
  highlights: BrandHighlight[]
}

function PortalTag({ label, onDark = false }: { label: string; onDark?: boolean }) {
  const tone = onDark ? 'border border-secondary-accent/40 bg-secondary-accent/15' : 'bg-secondary-accent-soft'
  return (
    <span className={`w-fit rounded-full px-3 py-1 font-body text-[11px] font-bold tracking-[1px] text-secondary-accent uppercase ${tone}`}>
      {label}
    </span>
  )
}

// A `Link` for a fixed destination, a button when the page must run its own
// handler first (the wizard's unsaved-changes guard, the OTP state reset).
export type BackAction = { to: string } | { onClick: () => void }

const BACK_CLASS =
  'flex size-10 shrink-0 cursor-pointer items-center justify-center rounded-full border border-sidebar-line bg-sidebar-raised/60 text-sidebar-text transition-colors hover:bg-sidebar-raised lg:size-9'

function BackControl({ back }: { back: BackAction }) {
  const icon = (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M10 3L5 8L10 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
  return 'to' in back ? (
    <Link to={back.to} aria-label="Back" className={BACK_CLASS}>
      {icon}
    </Link>
  ) : (
    <button type="button" onClick={back.onClick} aria-label="Back" className={BACK_CLASS}>
      {icon}
    </button>
  )
}

function LogoRow({ back, logoClassName }: { back?: BackAction; logoClassName: string }) {
  if (!back) return <BrandLogo variant="on-dark" className={logoClassName} />
  return (
    <div className="relative flex items-center gap-3">
      <BackControl back={back} />
      <BrandLogo variant="on-dark" className={logoClassName} />
    </div>
  )
}

// The brand side of the split. The lobby photo loads only on desktop, where
// the panel is shown: a hidden <picture> is still fetched by some browsers,
// and phones keep their download budget for the content. A page that fills
// the panel itself (the wizard's step list) gets plain navy, no photo.
function BrandPanel({
  brand,
  back,
  panel,
  panelClassName,
}: {
  brand: BrandCopy
  back?: BackAction
  panel?: ReactNode
  panelClassName: string
}) {
  const isDesktop = useIsDesktop()

  return (
    <aside className={`relative hidden shrink-0 flex-col justify-between overflow-hidden bg-sidebar px-12 py-10 short:py-8 lg:flex ${panelClassName}`}>
      <div aria-hidden className="absolute inset-0">
        {isDesktop && !panel && <HeroImage />}
        <div className="absolute inset-0 bg-gradient-to-br from-sidebar/95 via-sidebar/85 to-sidebar/60" />
        <div className="absolute -top-32 -left-32 size-[480px] rounded-full bg-secondary-accent/20 blur-3xl" />
      </div>

      <LogoRow back={back} logoClassName="relative h-8" />

      {panel ? (
        <div className="relative min-h-0 flex-1 overflow-y-auto py-10 short:py-6">{panel}</div>
      ) : (
        <div className="relative flex max-w-[460px] flex-col gap-8 short:gap-6">
          <div className="flex flex-col gap-4 short:gap-3">
            <h2 className="font-display text-[40px] leading-[1.1] font-bold text-sidebar-text short:text-[34px]">{brand.headline}</h2>
            <p className="font-body text-[16px] leading-relaxed text-sidebar-soft">{brand.tagline}</p>
          </div>
          <ul className="flex flex-col gap-4 short:gap-3">
            {brand.highlights.map((item) => (
              <li key={item.label} className="flex items-center gap-3">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-sidebar-line/70 bg-sidebar-raised/70 text-secondary-accent">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
                    <path d={item.icon} stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
                <span className="font-body text-[15px] font-medium text-sidebar-text">{item.label}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="relative font-body text-[12px] text-sidebar-muted">{copyrightLine()}</p>
    </aside>
  )
}

interface SplitScreenLayoutProps {
  portalLabel: string
  brand: BrandCopy
  footerLinks: FooterLink[]
  // Shown under the main content, e.g. a help line.
  aside?: ReactNode
  // Width of the content column; sign-in forms are narrower than the
  // landing page's cards.
  contentClassName?: string
  back?: BackAction
  // Replaces the brand panel's headline, tagline and highlights.
  panel?: ReactNode
  // The brand panel's width.
  panelClassName?: string
  // `start` for content that grows (the wizard, history, a track result),
  // so it doesn't jump as it lengthens.
  align?: 'center' | 'start'
  showPortalTag?: boolean
  children: ReactNode
}

// The shell of every public page (public-page-layout). Only the content
// panel scrolls; the brand panel, or the top strip below `lg`, stays in place.
export function SplitScreenLayout({
  portalLabel,
  brand,
  footerLinks,
  aside,
  contentClassName = 'max-w-[400px]',
  back,
  panel,
  panelClassName = 'w-[45%] xl:w-1/2 xl:px-16',
  align = 'center',
  showPortalTag = true,
  children,
}: SplitScreenLayoutProps) {
  return (
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-surface lg:flex-row">
      <BrandPanel brand={brand} back={back} panel={panel} panelClassName={panelClassName} />

      <header className="flex shrink-0 items-center justify-between gap-3 bg-gradient-to-r from-sidebar to-sidebar-raised px-4 py-4 md:px-8 lg:hidden">
        <LogoRow back={back} logoClassName="h-7" />
        <PortalTag label={portalLabel} onDark />
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto">
        <div className="flex min-h-full flex-col px-4 md:px-12">
          <div className={`flex flex-1 flex-col items-center py-8 xshort:py-5 ${align === 'center' ? 'justify-center' : 'justify-start'}`}>
            <div className={`auth-form-enter flex w-full flex-col gap-6 xshort:gap-4 ${contentClassName}`}>
              {/* Below `lg` the top strip carries the tag instead. */}
              {showPortalTag && (
                <div className="hidden lg:block">
                  <PortalTag label={portalLabel} />
                </div>
              )}
              {children}
              {aside}
            </div>
          </div>

          {/* On desktop the copyright sits in the brand panel, so a footer with no
              links has nothing left to show there. */}
          <footer
            className={`flex shrink-0 flex-col items-center gap-2 border-t border-border-subtle py-5 font-body text-[12px] text-text-muted max-lg:py-4 sm:flex-row sm:flex-wrap sm:justify-between xshort:py-3 ${footerLinks.length === 0 ? 'lg:hidden' : ''}`}
          >
            <p className="lg:hidden">{copyrightLine()}</p>
            {footerLinks.length > 0 && (
              <div className="flex flex-wrap justify-center gap-x-6 gap-y-1 lg:ml-auto">
                {footerLinks.map((link) => (
                  <a key={link.label} href={link.href} className="inline-flex min-h-10 items-center break-all hover:text-text lg:min-h-0">
                    {link.label}
                  </a>
                ))}
              </div>
            )}
          </footer>
        </div>
      </main>
    </div>
  )
}
