interface StepSidebarProps {
  steps: readonly string[]
  currentStep: number
  onStepSelect: (index: number) => void
}

export function StepSidebar({ steps, currentStep, onStepSelect }: StepSidebarProps) {
  return (
    <nav className="hidden w-[220px] shrink-0 flex-col gap-4 md:flex">
      {steps.map((label, index) => {
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
