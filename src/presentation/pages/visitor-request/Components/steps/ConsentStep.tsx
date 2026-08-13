import { Checkbox } from '../../../../components/ui/Checkbox'
import type { ConsentFormState } from '../../types'

const TERMS = [
  'I agree to comply with all security protocols and regulations of the premises during my visit.',
  'I consent to the collection and processing of my personal data for visitor management and security.',
  'I understand that my visit may be recorded via CCTV for security purposes.',
  'I agree to wear the visitor badge at all times while on the premises.',
  'I acknowledge that I must be accompanied by my host in restricted areas.',
  'I agree to declare all items I am carrying and submit to security screening if required.',
  'I understand that the organization reserves the right to deny or revoke access at any time.',
  'I confirm that all information provided in this application is true and accurate.',
]

interface ConsentStepProps {
  value: ConsentFormState
  onChange: (value: ConsentFormState) => void
  error?: string
}

export function ConsentStep({ value, onChange, error }: ConsentStepProps) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="text-h3 text-text">Consent Agreement</h3>
        <p className="text-body text-text-muted">Please read and accept the following terms and conditions before proceeding.</p>
      </div>
      <div className="flex flex-col gap-2 rounded-lg border border-border-subtle bg-surface p-4">
        <h4 className="text-body font-semibold text-text">Terms &amp; Conditions</h4>
        <ol className="flex flex-col gap-1 text-body text-text-muted">
          {TERMS.map((term, index) => (
            <li key={index}>
              {index + 1}. {term}
            </li>
          ))}
        </ol>
      </div>
      <div className="flex flex-col gap-2">
        <Checkbox checked={value.agreedTerms} onChange={(agreedTerms) => onChange({ ...value, agreedTerms })}>
          I have read and agree to the Terms &amp; Conditions above.
        </Checkbox>
        <Checkbox checked={value.agreedDataUse} onChange={(agreedDataUse) => onChange({ ...value, agreedDataUse })}>
          I consent to the collection and use of my personal data as described.
        </Checkbox>
        <Checkbox checked={value.agreedSafety} onChange={(agreedSafety) => onChange({ ...value, agreedSafety })}>
          I agree to follow all safety and security guidelines during my visit.
        </Checkbox>
      </div>
      {error && <p className="text-caption text-danger">{error}</p>}
    </div>
  )
}
