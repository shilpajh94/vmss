import type { ReactNode } from 'react'
import { SplitScreenLayout } from '../../../../components/layout/SplitScreenLayout'
import { VISITOR_BRAND, visitorFooterLinks } from '../../../../components/layout/visitor-brand'

interface OtpScreenLayoutProps {
  onBack: () => void
  // `start` for the history list, which grows as more visits load.
  align?: 'center' | 'start'
  contentClassName?: string
  children: ReactNode
}

export function OtpScreenLayout({ onBack, align, contentClassName = 'max-w-[480px]', children }: OtpScreenLayoutProps) {
  return (
    <SplitScreenLayout
      portalLabel="Visitor Portal"
      brand={VISITOR_BRAND}
      footerLinks={visitorFooterLinks()}
      back={{ onClick: onBack }}
      align={align}
      contentClassName={contentClassName}
    >
      {children}
    </SplitScreenLayout>
  )
}
