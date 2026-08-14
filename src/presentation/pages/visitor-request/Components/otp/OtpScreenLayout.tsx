import type { ReactNode } from 'react'
import heroImage from '../../../../../assets/images/lobby-hero.png'

interface OtpScreenLayoutProps {
  onBack: () => void
  children: ReactNode
}

export function OtpScreenLayout({ onBack, children }: OtpScreenLayoutProps) {
  return (
    <div className="relative flex w-full flex-1 flex-col">
      <div aria-hidden className="absolute inset-0">
        <img src={heroImage} alt="" className="size-full object-cover" />
        <div className="absolute inset-0 bg-primary/55" />
      </div>
      <div className="relative flex items-center gap-4 px-12 pt-10 pb-8">
        <button
          type="button"
          onClick={onBack}
          aria-label="Back"
          className="flex size-10 items-center justify-center rounded-full bg-white text-text"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              d="M10 3L5 8L10 13"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
        <h1 className="text-h1 text-white">Request a Visit</h1>
      </div>
      <div className="relative flex flex-1 justify-center px-12 pb-16">{children}</div>
    </div>
  )
}
