import type { Branch } from '../../../domain/entities/branch-schema'
import { isValidEmail } from '../../utils/is-valid-email'
import { isValidPhoneNumber } from '../../utils/is-valid-phone-number'

export type BranchFormValues = Omit<Branch, 'id'>
export type BranchFormErrors = Partial<Record<keyof BranchFormValues, string>>

// `BranchCreate`/`BranchUpdate` column limits in the API.
export const BRANCH_LIMITS = {
  name: 255,
  code: 50,
  city: 100,
  address: 500,
  contactEmail: 255,
  contactPhone: 50,
  notes: 2000,
} as const

const REQUIRED_FIELDS: Array<{ key: keyof BranchFormValues; message: string }> = [
  { key: 'name', message: 'Branch name is required.' },
  { key: 'code', message: 'Branch code is required.' },
  { key: 'city', message: 'Location/city is required.' },
  { key: 'country', message: 'Country is required.' },
  { key: 'address', message: 'Physical address is required.' },
  { key: 'contactPersonUserId', message: 'Contact person is required.' },
  { key: 'contactEmail', message: 'Contact email is required.' },
  { key: 'contactPhone', message: 'Contact phone is required.' },
]

// Shared by the create page and the edit modal, so the two can't drift.
export function validateBranchValues(values: BranchFormValues): BranchFormErrors {
  const errors: BranchFormErrors = {}
  for (const field of REQUIRED_FIELDS) {
    const value = values[field.key]
    if (!value || (typeof value === 'string' && !value.trim())) {
      errors[field.key] = field.message
    }
  }
  if (!errors.contactEmail && !isValidEmail(values.contactEmail)) {
    errors.contactEmail = 'Enter a valid email address.'
  }
  if (!errors.contactPhone && !isValidPhoneNumber(values.contactPhone)) {
    errors.contactPhone = 'Enter a valid phone number.'
  }
  return errors
}
