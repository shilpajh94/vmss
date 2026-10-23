import { CheckIcon } from './icons'

interface StepMarkerProps {
  stepNumber: number
  /** Current or completed - filled with the accent colour. */
  isReached: boolean
  /** Completed - the number crossfades to a checkmark. */
  isComplete: boolean
  /** Font size/weight for the number; sizes otherwise match across wizards. */
  textClassName: string
}

// The numbered step circle shared by the staff stepper and the visitor
// wizard's side rail. Number and checkmark are stacked and crossfaded so
// completing a step animates instead of swapping; both are aria-hidden
// because the step's label beside it is the accessible name.
export function StepMarker({ stepNumber, isReached, isComplete, textClassName }: StepMarkerProps) {
  return (
    <span
      aria-hidden="true"
      className={`step-motion relative flex size-7 shrink-0 items-center justify-center rounded-full transition-colors ${textClassName} ${
        isReached ? 'bg-secondary-accent text-on-accent' : 'bg-border text-text-secondary'
      }`}
    >
      <span className={`step-motion transition-[opacity,scale] ${isComplete ? 'scale-50 opacity-0' : 'scale-100 opacity-100'}`}>
        {stepNumber}
      </span>
      <CheckIcon
        strokeWidth={3}
        className={`step-motion absolute size-3.5 transition-[opacity,scale] ${isComplete ? 'scale-100 opacity-100' : 'scale-50 opacity-0'}`}
      />
    </span>
  )
}
