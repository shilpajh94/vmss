// Values must match the backend's `idProofType` enum for POST /invitations
// exactly (validated server-side against these 4 strings).
export const ID_PROOF_OPTIONS = [
  { value: 'Aadhaar Card', label: 'Aadhaar Card' },
  { value: 'Passport', label: 'Passport' },
  { value: 'Driving License', label: 'Driving License' },
  { value: 'Other', label: 'Other' },
]

export const ID_PROOF_ALLOWED_TYPES = ['image/png', 'image/jpeg', 'application/pdf']

export const PROFILE_IMAGE_ALLOWED_TYPES = ['image/png', 'image/jpeg']
