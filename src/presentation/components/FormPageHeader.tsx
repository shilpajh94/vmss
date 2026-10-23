import type { ReactNode } from 'react'
import { BackButton } from './BackButton'

interface FormPageHeaderProps {
  title: ReactNode
  description?: ReactNode
  // Navigates to the page's known parent route (see BackButton).
  onBack: () => void
}

// The back button and heading every admin create/edit page opens with, so
// their spacing, type scale and touch target stay the same everywhere.
export function FormPageHeader({ title, description, onBack }: FormPageHeaderProps) {
  return (
    <div className="flex items-center gap-4">
      <BackButton onClick={onBack} />
      <div className="flex min-w-0 flex-col gap-0.5">
        <h1 className="font-display text-xl font-bold text-text md:text-2xl">{title}</h1>
        {description ? <p className="font-body text-sm text-text-muted">{description}</p> : null}
      </div>
    </div>
  )
}
