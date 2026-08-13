import { WIZARD_STEPS } from '../types'

interface StepSidebarProps {
  currentStep: number
}

export function StepSidebar({ currentStep }: StepSidebarProps) {
  return (
    <nav className="flex w-[220px] flex-col gap-4">
      {WIZARD_STEPS.map((label, index) => {
        const stepNumber = index + 1
        const isActive = index === currentStep
        const isComplete = index < currentStep

        return (
          <div key={label} className="flex items-center gap-3">
            <span
              className={`flex size-7 shrink-0 items-center justify-center rounded-full text-caption font-semibold ${
                isActive || isComplete ? 'bg-secondary-accent text-white' : 'bg-border text-text-muted'
              }`}
            >
              {stepNumber}
            </span>
            <span className={`text-body ${isActive ? 'font-semibold text-text' : 'text-text-muted'}`}>{label}</span>
          </div>
        )
      })}
    </nav>
  )
}
