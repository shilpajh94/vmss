interface ExpandableTextProps {
  text: string | null | undefined
  className?: string
}

/** Renders admin-authored free text (a field's `helpText`) in full — the one
 * shared implementation every field type and step relies on for this, rather
 * than each rendering it separately.
 */
export function ExpandableText({ text, className }: ExpandableTextProps) {
  if (!text) return null

  return (
    <div className={className ?? 'flex flex-col items-start gap-1'}>
      <p className="whitespace-pre-wrap text-caption text-text-muted">{text}</p>
    </div>
  )
}
