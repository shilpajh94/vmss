import { useState } from 'react'

interface ExpandableTextProps {
  text: string | null | undefined
  className?: string
}

const SENTENCE_END_PATTERN = /[.!?](?:\s|$)/

function firstSentence(text: string): string {
  const match = SENTENCE_END_PATTERN.exec(text)
  if (!match) return text
  return text.slice(0, match.index + 1)
}

/** Renders admin-authored free text (a field's `helpText`) truncated to its
 * first sentence by default, with a "See more"/"See less" toggle when the
 * text has more to show — the one shared implementation every field type
 * and step relies on for this, rather than each rendering it separately.
 */
export function ExpandableText({ text, className }: ExpandableTextProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  if (!text) return null

  const preview = firstSentence(text)
  const isTruncated = preview.trim().length < text.trim().length

  return (
    <div className={className ?? 'flex flex-col items-start gap-1'}>
      <p className="whitespace-pre-wrap text-caption text-text-muted">{isTruncated && !isExpanded ? preview : text}</p>
      {isTruncated && (
        <button
          type="button"
          onClick={() => setIsExpanded((prev) => !prev)}
          className="font-body text-xs font-semibold text-primary"
        >
          {isExpanded ? 'See less' : 'See more'}
        </button>
      )}
    </div>
  )
}
