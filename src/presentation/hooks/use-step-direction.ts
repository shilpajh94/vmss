import { useState } from 'react'

export type StepDirection = 'forward' | 'backward' | 'none'

// Which way the wizard last moved, so the entering step can slide in from the
// matching side. Derived from the step index alone (the "store the previous
// value in state" pattern) rather than recorded by goNext/goBack/goToStep.
// 'none' until the first step change, so landing on the page plays nothing.
export function useStepDirection(currentStep: number): StepDirection {
  const [previousStep, setPreviousStep] = useState(currentStep)
  const [direction, setDirection] = useState<StepDirection>('none')

  if (currentStep !== previousStep) {
    setPreviousStep(currentStep)
    setDirection(currentStep > previousStep ? 'forward' : 'backward')
  }

  return direction
}
