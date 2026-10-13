import { useState } from 'react'
import { ChevronDownIcon } from '../../../components/icons'

interface StepProgressHeaderProps {
  steps: readonly string[]
  currentStep: number
  onStepSelect: (index: number) => void
}

// Phone-width stand-in for StepSidebar (visitor-request-wizard "Step
// navigation adapts to narrow viewports"): same `steps` list and the same
// "only completed steps are selectable" rule, so both always agree on what
// the configured steps are and where the visitor is.
export function StepProgressHeader({ steps, currentStep, onStepSelect }: StepProgressHeaderProps) {
  const [isListOpen, setIsListOpen] = useState(false)
  const total = steps.length
  const progressPercent = total > 0 ? Math.round(((currentStep + 1) / total) * 100) : 0

  return (
    <div className="flex w-full flex-col gap-3 rounded-2xl border border-border bg-surface p-4 md:hidden">
      <button
        type="button"
        onClick={() => setIsListOpen((open) => !open)}
        aria-expanded={isListOpen}
        className="flex min-h-10 w-full items-center justify-between gap-3 text-left"
      >
        <span className="flex min-w-0 flex-col">
          <span className="text-caption font-semibold text-text-muted">
            Step {Math.min(currentStep + 1, total)} of {total}
          </span>
          <span className="truncate text-body font-semibold text-text">{steps[currentStep]}</span>
        </span>
        <ChevronDownIcon className={`size-5 shrink-0 text-text-muted transition-transform ${isListOpen ? 'rotate-180' : ''}`} />
      </button>

      <div
        role="progressbar"
        aria-valuemin={1}
        aria-valuemax={total}
        aria-valuenow={currentStep + 1}
        aria-label="Registration progress"
        className="h-1.5 w-full overflow-hidden rounded-full bg-border"
      >
        <div className="step-motion h-full rounded-full bg-secondary-accent transition-[width]" style={{ width: `${progressPercent}%` }} />
      </div>

      {isListOpen && (
        <ol className="flex flex-col gap-1 border-t border-border-subtle pt-2">
          {steps.map((label, index) => {
            const isActive = index === currentStep
            const isComplete = index < currentStep
            return (
              <li key={label}>
                <button
                  type="button"
                  disabled={!isComplete}
                  onClick={() => {
                    onStepSelect(index)
                    setIsListOpen(false)
                  }}
                  className="flex min-h-10 w-full items-center gap-3 rounded-lg px-1 text-left enabled:cursor-pointer enabled:hover:bg-border-subtle"
                >
                  <span
                    className={`flex size-7 shrink-0 items-center justify-center rounded-full text-caption font-semibold ${
                      isActive || isComplete ? 'bg-secondary-accent text-white' : 'bg-border text-text-muted'
                    }`}
                  >
                    {index + 1}
                  </span>
                  <span className={`text-body ${isActive ? 'font-semibold text-text' : 'text-text-muted'}`}>{label}</span>
                </button>
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}
