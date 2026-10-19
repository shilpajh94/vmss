import type { ButtonHTMLAttributes } from 'react'
import { PRESS_FEEDBACK_CLASS } from './interactive'

interface PendingButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** True while the async action this button started is in flight. */
  pending?: boolean
  /** Accessible name while pending, e.g. "Saving…". The visible label stays put. */
  pendingLabel?: string
}

// A button that starts an async action (ui-motion "Action buttons show
// pending feedback while their action runs"). While pending, its label
// stays laid out but invisible - so the button keeps its exact width and
// nothing beside it shifts - with a spinner centered on top. It's disabled
// (no double submit) and exposes aria-busy. Styling is the caller's own
// className, so it drops into any existing button design; `relative` is
// the only layout class it adds.
export function PendingButton({
  pending = false,
  pendingLabel,
  disabled,
  className = '',
  type = 'button',
  children,
  ...rest
}: PendingButtonProps) {
  return (
    <button
      {...rest}
      type={type}
      disabled={disabled || pending}
      aria-busy={pending || undefined}
      aria-label={pending && pendingLabel ? pendingLabel : rest['aria-label']}
      className={`relative ${PRESS_FEEDBACK_CLASS} ${className}`}
    >
      {/* `contents` keeps the caller's flex/gap layout applying to the
          children directly; visibility still inherits through it. */}
      <span className={`contents ${pending ? 'invisible' : ''}`}>{children}</span>
      {pending && (
        <span aria-hidden className="absolute inset-0 flex items-center justify-center">
          <span className="inline-block size-4 animate-spin rounded-full border-2 border-current/30 border-t-current" />
        </span>
      )}
    </button>
  )
}
