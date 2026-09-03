// Canonical purpose-of-visit choices, shared between the visitor-request form
// (where these values are captured) and the staff/admin purpose filter (which
// must offer every possible purpose, not just ones present in already-loaded
// visit requests).
export const PURPOSE_OF_VISIT_OPTIONS = [
  { value: 'business-meeting', label: 'Business Meeting' },
  { value: 'interview', label: 'Interview' },
  { value: 'delivery', label: 'Delivery' },
  { value: 'personal-visit', label: 'Personal Visit' },
  { value: 'vendor-contractor', label: 'Vendor / Contractor' },
  { value: 'other', label: 'Other' },
]
