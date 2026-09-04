export type FilePreviewKind = 'image' | 'pdf' | 'none'

// Drives how upload widgets render a preview: a thumbnail for images, a PDF
// badge for PDFs (an <img> can't render a PDF blob URL), nothing otherwise.
export function getFilePreviewKind(fileName?: string): FilePreviewKind {
  if (!fileName) return 'none'
  if (/\.pdf$/i.test(fileName)) return 'pdf'
  if (/\.(png|jpe?g|gif|webp)$/i.test(fileName)) return 'image'
  return 'none'
}
