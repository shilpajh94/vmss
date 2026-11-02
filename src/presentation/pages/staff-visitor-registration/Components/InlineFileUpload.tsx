import { useId, useState } from 'react'
import { FileTextIcon, UploadIcon } from '../../../components/icons'
import { getFilePreviewKind } from '../../../utils/file-preview-kind'

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

interface InlineFileUploadProps {
  label: string
  allowedTypes: string[]
  fileName?: string
  previewUrl?: string
  onUpload: (file: File) => Promise<string>
  onFileRefChange: (fileRef: string | undefined, fileName: string | undefined) => void
  error?: string
  required?: boolean
}

export function InlineFileUpload({
  label,
  allowedTypes,
  fileName,
  previewUrl,
  onUpload,
  onFileRefChange,
  error: externalError,
  required,
}: InlineFileUploadProps) {
  const inputId = useId()
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | undefined>(undefined)
  const previewKind = getFilePreviewKind(fileName)

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
    <div className="flex min-w-0 flex-col gap-1.5">
      <div className="flex min-w-0 items-center gap-2">
        {previewUrl && previewKind === 'image' && <img src={previewUrl} alt="" className="size-10 shrink-0 rounded-lg border border-border object-cover" />}
        {previewUrl && previewKind === 'pdf' && (
          <span className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-border bg-danger/10 text-danger">
            <FileTextIcon className="size-5" />
          </span>
        )}
        <label
          htmlFor={inputId}
          title={fileName}
          className="flex h-10 min-w-0 cursor-pointer items-center justify-center gap-2 rounded-lg border border-border bg-surface px-4 text-[13px] font-semibold text-secondary-accent"
        >
          <UploadIcon className="size-4 shrink-0" />
          {/* A long file name truncates rather than overflowing the row. */}
          <span className="min-w-0 truncate">{uploading ? 'Uploading…' : (fileName ?? label)}</span>
          {required && !fileName && <span className="text-danger">*</span>}
        </label>
      </div>
      <input id={inputId} type="file" className="hidden" onChange={handleChange} disabled={uploading} />
      {(error ?? externalError) && <p className="text-caption text-danger">{error ?? externalError}</p>}
    </div>
  )
}
