import { Fragment } from 'react'
import { StepMarker } from '../../../components/StepMarker'

interface StepSidebarProps {
  steps: readonly string[]
  currentStep: number
  onStepSelect: (index: number) => void
}

export function StepSidebar({ steps, currentStep, onStepSelect }: StepSidebarProps) {
  // From `lg`: on a tablet the 220px rail left the form too narrow; the
  // compact progress header covers that width instead.
  return (
    <nav className="hidden w-[220px] shrink-0 flex-col lg:flex">
      {steps.map((label, index) => {
        const isActive = index === currentStep
        const isComplete = index < currentStep

        return (
          <Fragment key={label}>
            <button
              type="button"
              onClick={() => onStepSelect(index)}
              disabled={!isComplete}
              className={`flex items-center gap-3 text-left ${isComplete ? 'cursor-pointer' : 'cursor-default'}`}
            >
              <StepMarker stepNumber={index + 1} isReached={isActive || isComplete} isComplete={isComplete} textClassName="text-caption font-semibold" />
              <span className={`text-body ${isActive ? 'font-semibold text-text' : 'text-text-muted'}`}>{label}</span>
            </button>
            {index < steps.length - 1 && (
              // Centred under the 28px marker; fills downward once this step
              // is completed (visitor-request-wizard "Moving between steps is
              // animated"). Its height replaces the rail's former 16px gap.
              <div aria-hidden="true" className="relative my-1 ml-[13px] h-2 w-0.5 overflow-hidden rounded-full bg-border">
                <div
                  className={`step-motion absolute inset-0 origin-top bg-secondary-accent transition-transform ${
                    isComplete ? 'scale-y-100' : 'scale-y-0'
                  }`}
                />
              </div>
            )}
          </Fragment>
        )
      })}
    </nav>
  )
}
