import { useId, useState } from 'react'
import { UploadIcon } from '../../../components/icons'

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

interface InlineFileUploadProps {
  label: string
  allowedTypes: string[]
  fileName?: string
  onUpload: (file: File) => Promise<string>
  onFileRefChange: (fileRef: string | undefined, fileName: string | undefined) => void
}

export function InlineFileUpload({ label, allowedTypes, fileName, onUpload, onFileRefChange }: InlineFileUploadProps) {
  const inputId = useId()
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | undefined>(undefined)

  const handleChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    if (!allowedTypes.includes(file.type)) {
      setError('Unsupported file type.')
      onFileRefChange(undefined, undefined)
      return
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setError('File must be under 5MB.')
      onFileRefChange(undefined, undefined)
      return
    }

    setError(undefined)
    setUploading(true)
    try {
      const fileRef = await onUpload(file)
      onFileRefChange(fileRef, file.name)
    } catch {
      setError('Upload failed. Please try again.')
      onFileRefChange(undefined, undefined)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label
        htmlFor={inputId}
        className="flex h-10 shrink-0 cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-lg border border-border bg-surface px-4 text-[13px] font-semibold text-secondary-accent"
      >
        <UploadIcon className="size-4" />
        {uploading ? 'Uploading…' : (fileName ?? label)}
      </label>
      <input id={inputId} type="file" className="hidden" onChange={handleChange} disabled={uploading} />
      {error && <p className="text-caption text-danger">{error}</p>}
    </div>
  )
}
