import { WIZARD_STEPS } from '../types'

interface StepSidebarProps {
  currentStep: number
  onStepSelect: (index: number) => void
}

export function StepSidebar({ currentStep, onStepSelect }: StepSidebarProps) {
  return (
    <nav className="flex w-[220px] flex-col gap-4">
      {WIZARD_STEPS.map((label, index) => {
        const stepNumber = index + 1
        const isActive = index === currentStep
        const isComplete = index < currentStep

        return (
          <button
            key={label}
            type="button"
            onClick={() => onStepSelect(index)}
            disabled={!isComplete}
            className={`flex items-center gap-3 text-left ${isComplete ? 'cursor-pointer' : 'cursor-default'}`}
          >
            <span
              className={`flex size-7 shrink-0 items-center justify-center rounded-full text-caption font-semibold ${
                isActive || isComplete ? 'bg-secondary-accent text-white' : 'bg-border text-text-muted'
              }`}
            >
              {stepNumber}
            </span>
            <span className={`text-body ${isActive ? 'font-semibold text-text' : 'text-text-muted'}`}>{label}</span>
          </button>
        )
      })}
    </nav>
  )
}
