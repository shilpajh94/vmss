// Canonical purpose-of-visit choices, shared between the visitor-request form
// (where these values are captured) and the staff/admin purpose filter (which
// must offer every possible purpose, not just ones present in already-loaded
// visit requests). The label is what gets stored and matched on (QA F11);
// the slugs only survive in rows saved before that, read through
// `purposeLabel`.
const PURPOSES = [
  { slug: 'business-meeting', label: 'Business Meeting' },
  { slug: 'interview', label: 'Interview' },
  { slug: 'delivery', label: 'Delivery' },
  { slug: 'personal-visit', label: 'Personal Visit' },
  { slug: 'vendor-contractor', label: 'Vendor / Contractor' },
  { slug: 'other', label: 'Other' },
]

export const PURPOSE_OF_VISIT_OPTIONS = PURPOSES.map(({ label }) => ({ value: label, label }))

const LABEL_BY_SLUG = new Map(PURPOSES.map(({ slug, label }) => [slug, label]))

/** A stored purpose as shown to users: a legacy slug becomes its label. */
export function purposeLabel(value: string): string
export function purposeLabel(value: string | null | undefined): string | null | undefined
export function purposeLabel(value: string | null | undefined): string | null | undefined {
  return value ? (LABEL_BY_SLUG.get(value) ?? value) : value
}
