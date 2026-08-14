interface RegistrationStepperProps {
  steps: readonly string[]
  currentStep: number
}

export function RegistrationStepper({ steps, currentStep }: RegistrationStepperProps) {
  return (
    <div className="flex w-full items-center gap-3">
      {steps.map((label, index) => (
        <div key={label} className="contents">
          <div className="flex shrink-0 items-center gap-2">
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
          </div>
          {index < steps.length - 1 && <div className="h-px flex-1 bg-border" />}
        </div>
      ))}
    </div>
  )
}
