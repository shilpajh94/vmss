interface RegistrationStepperProps {
  steps: readonly string[]
  currentStep: number
  onStepSelect: (index: number) => void
}

export function RegistrationStepper({ steps, currentStep, onStepSelect }: RegistrationStepperProps) {
  return (
    <div className="flex w-full items-center gap-3">
      {steps.map((label, index) => {
        const isComplete = index < currentStep

        return (
          <div key={label} className="contents">
            <button
              type="button"
              onClick={() => onStepSelect(index)}
              disabled={!isComplete}
              className={`flex shrink-0 items-center gap-2 ${isComplete ? 'cursor-pointer' : 'cursor-default'}`}
            >
              <span
                className={`flex size-7 shrink-0 items-center justify-center rounded-full text-[13px] font-bold ${
                  index <= currentStep ? 'bg-secondary-accent text-white' : 'bg-border text-text-muted'
                }`}
              >
                {index + 1}
              </span>
              <span className={`text-[13px] whitespace-nowrap ${index === currentStep ? 'font-bold text-text' : 'font-semibold text-text-muted'}`}>
                {label}
              </span>
            </button>
            {index < steps.length - 1 && <div className="h-px flex-1 bg-border" />}
          </div>
        )
      })}
    </div>
  )
}
