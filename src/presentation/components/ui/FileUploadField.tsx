import { useId, useState } from 'react'

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

interface FileUploadFieldProps {
  label: string
  helperText?: string
  allowedTypes: string[]
  fileName?: string
  previewUrl?: string
  onUpload: (file: File) => Promise<string>
  onFileRefChange: (fileRef: string | undefined, fileName: string | undefined) => void
  error?: string
}

export function FileUploadField({
  label,
  helperText,
  allowedTypes,
  fileName,
  previewUrl,
  onUpload,
  onFileRefChange,
  error: externalError,
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
        className={`flex cursor-pointer items-center rounded-lg border border-dashed border-border bg-surface px-4 py-4 ${
          previewUrl ? 'gap-4' : 'flex-col gap-1 text-center py-6'
        }`}
      >
        {previewUrl && <img src={previewUrl} alt="" className="size-12 shrink-0 rounded-lg object-cover" />}
        <span className="flex flex-col gap-0.5">
          <span className="text-body font-semibold text-text">
            {uploading ? 'Uploading…' : fileName ? fileName : 'Click to upload or drag & drop'}
          </span>
          {helperText && <span className="text-caption text-text-muted">{helperText}</span>}
        </span>
      </label>
      <input id={inputId} type="file" className="hidden" onChange={handleChange} disabled={uploading} />
      {(error ?? externalError) && <p className="text-caption text-danger">{error ?? externalError}</p>}
    </div>
  )
}
