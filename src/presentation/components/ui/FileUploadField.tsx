import { useId, useState } from 'react'

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

interface FileUploadFieldProps {
  label: string
  helperText?: string
  allowedTypes: string[]
  fileName?: string
  onUpload: (file: File) => Promise<string>
  onFileRefChange: (fileRef: string | undefined, fileName: string | undefined) => void
}

export function FileUploadField({
  label,
  helperText,
  allowedTypes,
  fileName,
  onUpload,
  onFileRefChange,
}: FileUploadFieldProps) {
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
      <label htmlFor={inputId} className="text-body font-medium text-text">
        {label}
      </label>
      <label
        htmlFor={inputId}
        className="flex cursor-pointer flex-col items-center gap-1 rounded-lg border border-dashed border-border bg-surface px-4 py-6 text-center"
      >
        <span className="text-body text-text">
          {uploading ? 'Uploading…' : fileName ? fileName : 'Click to upload or drag & drop'}
        </span>
        {helperText && <span className="text-caption text-text-muted">{helperText}</span>}
      </label>
      <input id={inputId} type="file" className="hidden" onChange={handleChange} disabled={uploading} />
      {error && <p className="text-caption text-danger">{error}</p>}
    </div>
  )
}
