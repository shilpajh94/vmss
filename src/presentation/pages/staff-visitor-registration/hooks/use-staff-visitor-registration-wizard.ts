import { useRef, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { Branch } from '../../../../domain/entities/branch-schema'
import type { SubmissionStatus } from '../../visitor-request/Components/steps/ReviewConfirmStep'
import {
  createInitialStaffFormState,
  toStaffVisitRequest,
  type StaffVisitorFormEntry,
  type StaffVisitRequestFormState,
} from '../types'

function validateStaffVisitorContact(contact: StaffVisitorFormEntry): Record<string, string> {
  const errors: Record<string, string> = {}
  if (!contact.fullName) errors.fullName = 'Full name is required.'
  if (!contact.email) errors.email = 'Email is required.'
  if (!contact.phone) errors.phone = 'Phone number is required.'
  if (!contact.visitorCategory) errors.visitorCategory = 'Visitor category is required.'
  if (!contact.preferredContactMethod) errors.preferredContactMethod = 'Preferred contact method is required.'
  if (!contact.idProofType) errors.idProofType = 'ID proof type is required.'
  if (!contact.idProofFileRef) errors.idProofFileRef = 'ID proof file is required.'
  return errors
}

function validateStep(step: number, formState: StaffVisitRequestFormState): Record<string, string> {
  if (step === 0) {
    const errors = validateStaffVisitorContact(formState.primaryContact)
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

export function useStaffVisitorRegistrationWizard(branches?: Branch[]) {
  const { submitStaffVisitRequestUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentStep, setCurrentStep] = useState(0)
  const [formState, setFormState] = useState<StaffVisitRequestFormState>(createInitialStaffFormState)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submissionStatus, setSubmissionStatus] = useState<SubmissionStatus>('idle')
  const [trackingId, setTrackingId] = useState<string | undefined>(undefined)
  const [submissionError, setSubmissionError] = useState<string | undefined>(undefined)

  // POST /invitations wants ID-proof files travelling inline in the final
  // multipart submission, not pre-uploaded. `uploadFile` here just hands the
  // file a local ref so InlineFileUpload can track/display it; the real File
  // objects are recovered by that ref at submit time below.
  const fileRegistry = useRef(new Map<string, File>())

  const uploadFile = async (file: File): Promise<string> => {
    const fileRef = crypto.randomUUID()
    fileRegistry.current.set(fileRef, file)
    return fileRef
  }

  const updateFormState = (next: StaffVisitRequestFormState) => {
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

  const reset = () => {
    setFormState(createInitialStaffFormState())
    setCurrentStep(0)
    setErrors({})
    setSubmissionStatus('idle')
    setTrackingId(undefined)
    setSubmissionError(undefined)
  }

  const submit = async () => {
    const primaryContactIdProofFile = formState.primaryContact.idProofFileRef
      ? fileRegistry.current.get(formState.primaryContact.idProofFileRef)
      : undefined
    const branchId = branches?.find((branch) => branch.name === formState.visitInfo.location)?.id
    if (!primaryContactIdProofFile || !branchId) {
      setSubmissionError('Something went wrong submitting your request. Please try again.')
      setSubmissionStatus('error')
      toast.error('Something went wrong submitting your request. Please try again.')
      return
    }

    const visitorIdProofFiles = formState.additionalVisitors
      .map((visitor) => (visitor.idProofFileRef ? fileRegistry.current.get(visitor.idProofFileRef) : undefined))
      .filter((file): file is File => file !== undefined)

    setSubmissionStatus('submitting')
    setSubmissionError(undefined)
    try {
      const response = await submitStaffVisitRequestUseCase.execute(
        toStaffVisitRequest(formState),
        { primaryContactIdProofFile, visitorIdProofFiles },
        branchId,
      )
      setTrackingId(response.trackingId)
      setSubmissionStatus('success')
      toast.success('Visitor registered successfully.')
    } catch {
      setSubmissionError('Something went wrong submitting your request. Please try again.')
      setSubmissionStatus('error')
      toast.error('Something went wrong submitting your request. Please try again.')
    }
  }

  return {
    currentStep,
    formState,
    setFormState: updateFormState,
    errors,
    goNext,
    goBack,
    uploadFile,
    submissionStatus,
    trackingId,
    submissionError,
    submit,
    reset,
  }
}
