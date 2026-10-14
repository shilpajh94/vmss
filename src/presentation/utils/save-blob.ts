// Saves a downloaded Blob under `filename` via a temporary object-URL link —
// for authenticated downloads that can't be plain browser navigations (no
// Authorization header would be sent).
export function saveBlob(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(objectUrl)
}
