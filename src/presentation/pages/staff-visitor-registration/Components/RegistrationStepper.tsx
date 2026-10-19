import { StepMarker } from '../../../components/StepMarker'

interface RegistrationStepperProps {
  steps: readonly string[]
  currentStep: number
  onStepSelect: (index: number) => void
}

export function RegistrationStepper({ steps, currentStep, onStepSelect }: RegistrationStepperProps) {
  return (
    <div className="w-full">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
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
                <StepMarker stepNumber={index + 1} isReached={index <= currentStep} isComplete={isComplete} textClassName="text-[13px] font-bold" />
                <span className={`text-[13px] whitespace-nowrap ${index === currentStep ? 'font-bold text-text' : 'font-semibold text-text-muted'}`}>
                  {label}
                </span>
              </button>
              {index < steps.length - 1 && (
                // Fills toward the next step once this one is completed, and
                // un-fills on the way back (staff-visitor-registration "Moving
                // between steps is animated").
                <div aria-hidden="true" className="relative h-0.5 w-8 shrink-0 overflow-hidden rounded-full bg-border">
                  <div
                    className={`step-motion absolute inset-0 origin-left bg-secondary-accent transition-transform ${
                      index < currentStep ? 'scale-x-100' : 'scale-x-0'
                    }`}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
