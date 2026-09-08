import { useState } from 'react'
import { SelectField } from '../../../components/ui/SelectField'
import { TextField } from '../../../components/ui/TextField'
import { isValidPhoneNumber } from '../../../utils/is-valid-phone-number'
import { createEmptyStaffVisitorFormEntry, type StaffVisitorFormEntry } from '../types'
import { ID_PROOF_ALLOWED_TYPES, ID_PROOF_OPTIONS } from './constants'
import { InlineFileUpload } from './InlineFileUpload'

interface AddVisitorFormProps {
  initialValue?: StaffVisitorFormEntry
  uploadFile: (file: File) => Promise<string>
  getFilePreviewUrl?: (fileRef?: string) => string | undefined
  onAdd: (visitor: StaffVisitorFormEntry) => void
  onCancel: () => void
}

export function AddVisitorForm({ initialValue, uploadFile, getFilePreviewUrl, onAdd, onCancel }: AddVisitorFormProps) {
  const [draft, setDraft] = useState<StaffVisitorFormEntry>(initialValue ?? createEmptyStaffVisitorFormEntry())
  const [error, setError] = useState<string | undefined>(undefined)

  const handleAdd = () => {
    if (!draft.fullName || !draft.idProofType) {
      setError('Full name and ID proof type are required.')
      return
    }
    if (!draft.email && !draft.phone) {
      setError('Either email or phone is required.')
      return
    }
    if (draft.phone && !isValidPhoneNumber(draft.phone)) {
      setError('Enter a valid phone number.')
      return
    }
    if (!draft.idProofFileRef) {
      setError('ID proof file is required.')
      return
    }
    setError(undefined)
    onAdd(draft)
  }

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-border bg-border-subtle p-5">
      <h4 className="font-display text-sm font-bold text-text">Add New Visitor</h4>

      <div className="grid grid-cols-3 gap-4">
        <TextField label="Full Name" placeholder="Full name" value={draft.fullName} onChange={(fullName) => setDraft({ ...draft, fullName })} />
        <TextField label="Email" placeholder="Email address" type="email" value={draft.email} onChange={(email) => setDraft({ ...draft, email })} />
        <TextField label="Phone" placeholder="Phone number" type="tel" value={draft.phone} onChange={(phone) => setDraft({ ...draft, phone })} />
      </div>

      <div className="flex items-end gap-3">
        <div className="flex-1">
          <SelectField
            label="ID Proof Type"
            placeholder="Select ID type"
            options={ID_PROOF_OPTIONS}
            value={draft.idProofType}
            onChange={(idProofType) => setDraft({ ...draft, idProofType })}
          />
        </div>
        <InlineFileUpload
          label="Upload ID File"
          allowedTypes={ID_PROOF_ALLOWED_TYPES}
          fileName={draft.idProofFileName}
          previewUrl={getFilePreviewUrl?.(draft.idProofFileRef)}
          onUpload={uploadFile}
          onFileRefChange={(idProofFileRef, idProofFileName) => setDraft({ ...draft, idProofFileRef, idProofFileName })}
          required
        />
      </div>

      {error && <p className="text-caption text-danger">{error}</p>}

      <div className="flex items-center justify-end gap-4">
        <button type="button" onClick={onCancel} className="text-[13px] font-semibold text-secondary-accent underline">
          Cancel
        </button>
        <button type="button" onClick={handleAdd} className="rounded-lg bg-secondary-accent px-5 py-2.5 text-[13px] font-semibold text-white">
          {initialValue ? 'Save Changes' : 'Add to List'}
        </button>
      </div>
    </div>
  )
}
