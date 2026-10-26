import { Fragment } from 'react'
import { StepMarker } from '../../../components/StepMarker'

interface StepSidebarProps {
  steps: readonly string[]
  currentStep: number
  onStepSelect: (index: number) => void
}

// The wizard's step list, drawn on the split-screen layout's navy panel
// (modernize-visitor-flow-pages D4). From `lg`, like the panel itself; the
// compact progress header covers narrower widths.
export function StepSidebar({ steps, currentStep, onStepSelect }: StepSidebarProps) {
  return (
    <nav aria-label="Registration steps" className="hidden w-full flex-col lg:flex">
      <p className="mb-5 font-body text-[11px] font-bold tracking-[1px] text-secondary-accent uppercase">Request a visit</p>
      {steps.map((label, index) => {
        const isActive = index === currentStep
        const isComplete = index < currentStep

        return (
          <Fragment key={label}>
            <button
              type="button"
              onClick={() => onStepSelect(index)}
              disabled={!isComplete}
              aria-current={isActive ? 'step' : undefined}
              className={`flex items-center gap-3 rounded-lg text-left ${isComplete ? 'group cursor-pointer' : 'cursor-default'}`}
            >
              <StepMarker
                stepNumber={index + 1}
                isReached={isActive || isComplete}
                isComplete={isComplete}
                textClassName="text-caption font-semibold"
                onDark
              />
              <span
                className={`font-body text-[15px] transition-colors ${
                  isActive ? 'font-semibold text-sidebar-text' : isComplete ? 'text-sidebar-soft group-hover:text-sidebar-text' : 'text-sidebar-muted'
                }`}
              >
                {label}
              </span>
            </button>
            {index < steps.length - 1 && (
              // Centred under the 28px marker; fills downward once this step
              // is completed (visitor-request-wizard "Moving between steps is
              // animated").
              <div aria-hidden="true" className="relative my-1.5 ml-[13px] h-4 w-0.5 overflow-hidden rounded-full bg-sidebar-line">
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
