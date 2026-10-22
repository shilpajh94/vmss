import { useState, type CSSProperties } from 'react'
import { initialsFor } from '../../utils/initials'

const SIZE_CLASSES = {
  sm: 'size-7 text-[11px]',
  md: 'size-8 text-xs',
  lg: 'size-9 text-[13px]',
  xl: 'size-11 text-sm',
} as const

// The reference initials badge (the staff top bar's signed-in user badge).
const DEFAULT_TONE = 'border-[1.5px] border-info bg-info/8 text-info'

interface AvatarProps {
  name: string
  photoUrl?: string | null
  size?: keyof typeof SIZE_CLASSES
  /** Replaces the default initials tone, for surfaces with an established look of their own. */
  toneClassName?: string
  style?: CSSProperties
}

// A person's photo when there is one, otherwise their initials. Photo URLs
// are often short-lived signed links, so a photo that fails to load falls
// back to initials instead of a broken-image icon. The initials are
// aria-hidden because every caller renders the person's name beside them.
export function Avatar({ name, photoUrl, size = 'lg', toneClassName = DEFAULT_TONE, style }: AvatarProps) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  const sizeClassName = SIZE_CLASSES[size]

  if (photoUrl && failedUrl !== photoUrl) {
    return (
      <img
        src={photoUrl}
        alt={name}
        onError={() => setFailedUrl(photoUrl)}
        className={`shrink-0 rounded-full object-cover ${sizeClassName}`}
      />
    )
  }

  return (
    <span
      aria-hidden="true"
      style={style}
      className={`flex shrink-0 items-center justify-center rounded-full font-display font-bold ${sizeClassName} ${toneClassName}`}
    >
      {initialsFor(name)}
    </span>
  )
}
