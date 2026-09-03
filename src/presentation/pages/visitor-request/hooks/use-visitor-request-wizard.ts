import { useRef, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import {
  createInitialFormState,
  toVisitRequest,
  type RegistrationType,
  type VisitorFormEntry,
  type VisitRequestFormState,
} from '../types'
import type { SubmissionStatus } from '../Components/steps/ReviewConfirmStep'

export interface VisitorRequestWizardInitialData {
  registrationType?: RegistrationType
  primaryContact?: Partial<Pick<VisitorFormEntry, 'email' | 'phone'>>
}

function buildInitialFormState(initial?: VisitorRequestWizardInitialData): VisitRequestFormState {
  const formState = createInitialFormState()
  if (initial?.registrationType) formState.registrationType = initial.registrationType
  if (initial?.primaryContact) formState.primaryContact = { ...formState.primaryContact, ...initial.primaryContact }
  return formState
}

function validateVisitorContact(contact: VisitorFormEntry): Record<string, string> {
  const errors: Record<string, string> = {}
  if (!contact.fullName) errors.fullName = 'Full name is required.'
  if (!contact.email) errors.email = 'Email is required.'
  if (!contact.phone) errors.phone = 'Phone number is required.'
  if (!contact.address) errors.address = 'Address is required.'
  if (!contact.visitorCategory) errors.visitorCategory = 'Visitor category is required.'
  if (!contact.idProofType) errors.idProofType = 'ID proof type is required.'
  if (!contact.idProofFileRef) errors.idProofFileRef = 'ID proof file is required.'
  return errors
}

function validateStep(step: number, formState: VisitRequestFormState): Record<string, string> {
  if (step === 0) {
    const errors = validateVisitorContact(formState.primaryContact)
    if (formState.registrationType === 'group' && formState.additionalVisitors.length === 0) {
      errors.additionalVisitors = 'Add at least one visitor to continue.'
    }
    return errors
  }

  if (step === 1) {
    const errors: Record<string, string> = {}
    const { visitInfo } = formState
    if (!visitInfo.purpose) errors.purpose = 'Purpose of visit is required.'
    if (!visitInfo.hostNameOrEmail) errors.hostNameOrEmail = 'Host name or email is required.'
    else if (!visitInfo.hostId) errors.hostNameOrEmail = 'Please select a host from the list.'
    if (!visitInfo.preferredDate) errors.preferredDate = 'Preferred visit date is required.'
    if (!visitInfo.preferredTime) errors.preferredTime = 'Preferred visit time is required.'
    if (!visitInfo.expectedDuration) errors.expectedDuration = 'Expected duration is required.'
    if (!visitInfo.location) errors.location = 'Location is required.'
    if (!visitInfo.building) errors.building = 'Building is required.'
    if (!visitInfo.department) errors.department = 'Department to visit is required.'
    return errors
  }

  if (step === 4) {
    const { consent } = formState
    if (!consent.agreedTerms || !consent.agreedDataUse || !consent.agreedSafety) {
      return { consent: 'You must agree to all three items to continue.' }
    }
    return {}
  }

  return {}
}

export function useVisitorRequestWizard(initial?: VisitorRequestWizardInitialData) {
  const { submitVisitRequestUseCase } = useAppDependencies()

  const [currentStep, setCurrentStep] = useState(0)
  const [formState, setFormState] = useState<VisitRequestFormState>(() => buildInitialFormState(initial))
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submissionStatus, setSubmissionStatus] = useState<SubmissionStatus>('idle')
  const [trackingId, setTrackingId] = useState<string | undefined>(undefined)
  const [submissionError, setSubmissionError] = useState<string | undefined>(undefined)

  // POST /registrations/walk-in wants ID-proof files travelling inline in the
  // final multipart submission, not pre-uploaded. `uploadFile` here just hands
  // the file a local ref so FileUploadField can track/display it; the real
  // File objects are recovered by that ref at submit time below.
  const fileRegistry = useRef(new Map<string, File>())

  const uploadFile = async (file: File): Promise<string> => {
    const fileRef = crypto.randomUUID()
    fileRegistry.current.set(fileRef, file)
    return fileRef
  }

  const updateFormState = (next: VisitRequestFormState) => {
    setFormState(next)
    // Clear stale step errors optimistically; goNext re-validates before advancing.
    setErrors({})
  }

  const goNext = () => {
    const stepErrors = validateStep(currentStep, formState)
    if (Object.keys(stepErrors).length > 0) {
      setErrors(stepErrors)
      return
    }
    setErrors({})
    setCurrentStep((step) => Math.min(step + 1, 5))
  }

  const goBack = () => {
    setErrors({})
    setCurrentStep((step) => Math.max(step - 1, 0))
  }

  // Jumping to an already-completed step (e.g. via the sidebar) never needs
  // re-validation — only forward movement via goNext does.
  const goToStep = (step: number) => {
    if (step >= currentStep) return
    setErrors({})
    setCurrentStep(step)
  }

  const submit = async () => {
    const primaryContactIdProofFile = formState.primaryContact.idProofFileRef
      ? fileRegistry.current.get(formState.primaryContact.idProofFileRef)
      : undefined
    if (!primaryContactIdProofFile) {
      setSubmissionError('Something went wrong submitting your request. Please try again.')
      setSubmissionStatus('error')
      return
    }

    const visitorIdProofFiles = formState.additionalVisitors
      .map((visitor) => (visitor.idProofFileRef ? fileRegistry.current.get(visitor.idProofFileRef) : undefined))
      .filter((file): file is File => file !== undefined)

    setSubmissionStatus('submitting')
    setSubmissionError(undefined)
    try {
      const response = await submitVisitRequestUseCase.execute(toVisitRequest(formState), {
        primaryContactIdProofFile,
        visitorIdProofFiles,
      })
      setTrackingId(response.trackingId)
      setSubmissionStatus('success')
    } catch (error) {
      setSubmissionError(error instanceof Error ? error.message : 'Something went wrong submitting your request. Please try again.')
      setSubmissionStatus('error')
    }
  }

  return {
    currentStep,
    formState,
    setFormState: updateFormState,
    errors,
    goNext,
    goBack,
    goToStep,
    uploadFile,
    submissionStatus,
    trackingId,
    submissionError,
    submit,
  }
}
